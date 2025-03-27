import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Literal, Self

import ulid
from pydantic import BaseModel, RootModel, Field, field_validator, computed_field, model_validator, model_serializer, field_serializer

from aicore.logger import _logger
from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE, DEFAULT_ENCODING
from aicore.observability.models import Base, Session, Message, Metric

class LlmOperationRecord(BaseModel):
    """Data model for storing information about a single LLM operation."""
    session_id: Optional[str] = ""
    workspace: Optional[str] = ""
    agent_id: Optional[str] = ""
    action_id: Optional[str] = ""
    operation_id: str = Field(default_factory=ulid.ulid)
    timestamp: Optional[str] = ""
    operation_type: Literal["completion", "acompletion"]
    provider: str
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    cost: Optional[float] = 0
    latency_ms: float
    error_message: Optional[str] = ""
    completion_args: Union[Dict[str, Any], str]
    response: Optional[Union[str, Dict, List]] = ""

    class Config:
        arbitrary_types_allowed = True

    @field_validator(*["session_id", "workspace", "agent_id", "action_id", "timestamp", "error_message", "response"])
    @classmethod
    def ensure_non_nulls(cls, value: Optional[str] = None) -> str:
        if value is None:
            return ""
        return value

    @field_validator("response")
    @classmethod
    def json_dumps_response(cls, response: Union[None, str, Dict[str, str]]) -> Optional[str]:
        if isinstance(response, (str, type(None))):
            return response
        elif isinstance(response, (dict, list)):
            return json.dumps(response, indent=4)
        else:
            raise TypeError("response param must be [str] or [json serializable obj]")

    @field_validator("completion_args")
    @classmethod
    def json_laods_response(cls, args: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(args, str):
            return json.loads(args)
        elif isinstance(args, dict):
            return args

    @model_validator(mode="after")
    def init_workspace_and_timestamp(self) -> Self:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        self.workspace = self.workspace or os.environ.get("WORKSPACE", "")
        return self

    @field_serializer("completion_args", when_used='json')
    def json_dump_completion_args(self, completion_args: Dict[str, Any]) -> str:
        return json.dumps(completion_args, indent=4)

    @property
    def messages(self) -> List[Dict[str, str]]:
        return self.completion_args.get("messages", [])

    @computed_field
    def model(self) -> str:
        return self.completion_args.get("model", "")

    @computed_field
    def temperature(self) -> float:
        return self.completion_args.get("temperature", 0.0)

    @computed_field
    def max_tokens(self) -> int:
        return self.completion_args.get("max_tokens", 0) or self.completion_args.get("max_completion_tokens", 0)

    @computed_field
    def system_prompt(self) -> Optional[str]:
        for msg in self.messages:
            if msg.get("role") == "system":
                return msg.get("content", "")
        # anthropic system messages
        if self.completion_args.get("system"):
            return self.completion_args.get("system")
                
        return ""

    @computed_field
    def assistant_message(self) -> Optional[str]:
        for msg in self.messages[::-1]:
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""

    @computed_field
    def user_prompt(self) -> Optional[str]:
        for msg in self.messages[::-1]:
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @computed_field
    def history_messages(self) -> Optional[str]:
        return json.dumps([
            msg for msg in self.messages
            if msg.get("content") not in [
                self.system_prompt,
                self.assistant_message,
                self.user_prompt
            ]
        ], indent=4)

    @computed_field
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @computed_field
    def success(self) -> bool:
        return bool(self.response)

    @model_serializer
    def serialize_model(self) -> Dict[str, Any]:
        """Ensure a cohesive field order during serialization."""
        return {
            "session_id": self.session_id,
            "workspace": self.workspace,
            "agent_id": self.agent_id,
            "action_id": self.action_id,
            "timestamp": self.timestamp,
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response": self.response,
            "success": self.success,
            "assistant_message": self.assistant_message,
            "history_messages": self.history_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "completion_args": json.dumps(self.completion_args, indent=4)
        }
    


class LlmOperationCollector(RootModel):
    root: List[LlmOperationRecord] = []
    _storage_path: Optional[Union[str, Path]] = None
    _table_initialized :Optional[bool]=False
    _last_inserted_record :Optional[str]=None
    _engine :Optional[Any]=None
    _async_engine: Optional[Any] = None
    _dbsession :Optional[Any]=None
    _adbsession: Optional[Any] = None

    @model_validator(mode="after")
    def init_dbsession(self) -> Self:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
            from dotenv import load_dotenv
            load_dotenv()
            conn_str = os.environ.get("CONNECTION_STRING")
            async_conn_str = os.environ.get("ASYNC_CONNECTION_STRING")  # Add async DB connectio
            try:
                if conn_str:
                    self.engine = create_engine(conn_str)
                    self.DBSession = sessionmaker(bind=self.engine)
                    Base.metadata.create_all(self.engine)
                    self._table_initialized = True 
                # Async Engine
                if async_conn_str:
                    self.async_engine = create_async_engine(async_conn_str)
                    self.aDBSession = async_sessionmaker(bind=self.async_engine, class_=AsyncSession)
                
            except Exception as e:
                    _logger.logger.warning(f"Database connection failed: {str(e)}")

        except ModuleNotFoundError:
            raise ModuleNotFoundError("pip install aicore[pg] for postgress integration and setup PG_CONNECTION_STRING env var")
        return self
    
    async def create_tables(self):
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            self._table_initialized = True 

    @property
    def storage_path(self) -> Optional[Union[str, Path]]:
        return self._storage_path

    @property
    def async_engine(self):
        return self._async_engine
    
    @async_engine.setter
    def async_engine(self, engine):
        self._async_engine = engine
    
    @property
    def engine(self):
        return self._engine
    
    @engine.setter
    def engine(self, engine):
        self._engine = engine

    @property
    def DBSession(self):
        return self._dbsession
    
    @DBSession.setter
    def DBSession(self, session):
        self._dbsession = session

    @property
    def aDBSession(self):
        return self._adbsession
    
    @aDBSession.setter
    def aDBSession(self, session):
        self._adbsession = session    

    @storage_path.setter
    def storage_path(self, value: Union[str, Path]):
        self._storage_path = value

    def _store_to_file(self, new_record: LlmOperationRecord) -> None:
        if not os.path.exists(self.storage_path):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            records = LlmOperationCollector()
        else:
            with open(self.storage_path, 'r', encoding=DEFAULT_ENCODING) as f:                
                records = LlmOperationCollector(root=[LlmOperationRecord(**kwargs) for kwargs in json.loads(f.read())])
        records.root.append(new_record)

        with open(self.storage_path, 'w', encoding=DEFAULT_ENCODING) as f:
            f.write(records.model_dump_json(indent=4))

    @staticmethod
    def _clean_completion_args(args: Dict[str, Any]) -> Dict[str, Any]:
        """Clean request arguments to remove sensitive information."""
        cleaned = args.copy()
        # Remove potentially sensitive information like API keys
        cleaned.pop("api_key", None)
        return cleaned

    @classmethod
    def fom_observable_storage_path(cls, storage_path: Optional[str] = None) -> "LlmOperationCollector":
        obj = cls()
        env_path = os.environ.get("OBSERVABILITY_DATA_DEFAULT_FILE")
        if storage_path:
            obj.storage_path = storage_path
        elif env_path:
            obj.storage_path = env_path
        else:
            obj.storage_path = Path(DEFAULT_OBSERVABILITY_DIR) / DEFAULT_OBSERVABILITY_FILE
        return obj

    @classmethod
    def polars_from_file(cls, storage_path: Optional[str] = None) -> "pl.DataFrame":  # noqa: F821
        obj = cls.fom_observable_storage_path(storage_path)
        if os.path.exists(obj.storage_path):
            with open(obj.storage_path, 'r', encoding=DEFAULT_ENCODING) as f:
                obj = cls(root=json.loads(f.read()))
        try:
            import polars as pl
            dicts = obj.model_dump()
            return pl.from_dicts(dicts) if dicts else pl.DataFrame()
        except ModuleNotFoundError:
            _logger.logger.warning("pip install -r requirements-dashboard.txt")
            return None
    
    def _handle_record(
        self,
        completion_args: Dict[str, Any],
        operation_type: Literal["completion", "acompletion"],
        provider: str,
        response: Optional[Union[str, Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        input_tokens: Optional[int] = 0,
        output_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> LlmOperationRecord:
        # Clean request args
        cleaned_args = self._clean_completion_args(completion_args)
        
        # Build a record
        record = LlmOperationRecord(
            session_id=session_id,
            agent_id=agent_id,
            action_id=action_id,
            workspace=workspace,
            provider=provider,
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            latency_ms=latency_ms or 0,
            error_message=error_message,
            completion_args=cleaned_args,
            response=response
        )
        
        if self.storage_path:
            self._store_to_file(record)
        
        self.root.append(record)

        return record        

    def record_completion(
        self,
        completion_args: Dict[str, Any],
        operation_type: Literal["completion", "acompletion"],
        provider: str,
        response: Optional[Union[str, Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        input_tokens: Optional[int] = 0,
        output_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> LlmOperationRecord:
        # Clean request args
        record = self._handle_record(
            completion_args, operation_type, provider, response, 
            session_id, workspace, agent_id, action_id, 
            input_tokens, output_tokens, cost, latency_ms, error_message
        )
        
        if self.engine and self.DBSession:
            try:
                self._insert_record_to_db(record)
            except Exception as e:
                _logger.logger.error(f"Error inserting record to DB: {str(e)}")
        
        return record
    
    async def arecord_completion(
        self,
        completion_args: Dict[str, Any],
        operation_type: Literal["completion", "acompletion"],
        provider: str,
        response: Optional[Union[str, Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        input_tokens: Optional[int] = 0,
        output_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> LlmOperationRecord:
        # Clean request args
        record = self._handle_record(
            completion_args, operation_type, provider, response, 
            session_id, workspace, agent_id, action_id, 
            input_tokens, output_tokens, cost, latency_ms, error_message
        )
        
        if self.async_engine and self.aDBSession:
            await self.create_tables()
            try:
                await self._a_insert_record_to_db(record)
            except Exception as e:
                _logger.logger.error(f"Error inserting record to DB: {str(e)}")
        
        return record
    
    def _insert_record_to_db(self, record: LlmOperationRecord) -> None:
        """Insert a single LLM operation record into the database using SQLAlchemy."""
        if not self.DBSession:
            if self.aDBSession:
                _logger.logger.warning("You have configured an async connection to a db but are trying to establish a sync one. Pass CONNECTION_STRING env var.")
            return
            
        serialized = record.serialize_model()
        session = self.DBSession()
        
        try:
            # Check if session exists, create if it doesn't
            db_session = session.query(Session).filter_by(session_id=serialized['session_id']).first()
            if not db_session:
                db_session = Session(
                    session_id=serialized['session_id'],
                    workspace=serialized['workspace'],
                    agent_id=serialized['agent_id']
                )
                session.add(db_session)
            
            # Create message record
            message = Message(
                operation_id=serialized['operation_id'],
                session_id=serialized['session_id'],
                action_id=serialized['action_id'],
                timestamp=serialized['timestamp'],
                system_prompt=serialized['system_prompt'],
                user_prompt=serialized['user_prompt'],
                response=serialized['response'],
                assistant_message=serialized['assistant_message'],
                history_messages=serialized['history_messages'],
                completion_args=serialized['completion_args'],
                error_message=serialized['error_message']
            )
            session.add(message)
            
            # Create metrics record
            metric = Metric(
                operation_id=serialized['operation_id'],
                operation_type=serialized['operation_type'],
                provider=serialized['provider'],
                model=serialized['model'],
                success=serialized['success'],
                temperature=serialized['temperature'],
                max_tokens=serialized['max_tokens'],
                input_tokens=serialized['input_tokens'],
                output_tokens=serialized['output_tokens'],
                total_tokens=serialized['total_tokens'],
                cost=serialized['cost'],
                latency_ms=serialized['latency_ms']
            )
            session.add(metric)
            
            # Commit all changes
            session.commit()
            self._last_inserted_record = serialized['operation_id']
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    async def _a_insert_record_to_db(self, record: LlmOperationRecord) -> None:
        """Insert a single LLM operation record into the database asynchronously."""
        if not self.aDBSession:
            if self.DBSession:
                _logger.logger.warning("You have configured a sync connection to a db but are trying to establish an async one. Pass ASYNC_CONNECTION_STRING env var.")
            return

        serialized = record.serialize_model()
        async with self.aDBSession() as session:
            try:
                from sqlalchemy.future import select
                # Check if session exists, create if it doesn't
                result = await session.execute(select(Session).filter_by(session_id=serialized['session_id']))
                db_session = result.scalars().first()
                
                if not db_session:
                    db_session = Session(
                        session_id=serialized['session_id'],
                        workspace=serialized['workspace'],
                        agent_id=serialized['agent_id']
                    )
                    session.add(db_session)

                # Create message record
                message = Message(
                    operation_id=serialized['operation_id'],
                    session_id=serialized['session_id'],
                    action_id=serialized['action_id'],
                    timestamp=serialized['timestamp'],
                    system_prompt=serialized['system_prompt'],
                    user_prompt=serialized['user_prompt'],
                    response=serialized['response'],
                    assistant_message=serialized['assistant_message'],
                    history_messages=serialized['history_messages'],
                    completion_args=serialized['completion_args'],
                    error_message=serialized['error_message']
                )
                session.add(message)

                # Create metrics record
                metric = Metric(
                    operation_id=serialized['operation_id'],
                    operation_type=serialized['operation_type'],
                    provider=serialized['provider'],
                    model=serialized['model'],
                    success=serialized['success'],
                    temperature=serialized['temperature'],
                    max_tokens=serialized['max_tokens'],
                    input_tokens=serialized['input_tokens'],
                    output_tokens=serialized['output_tokens'],
                    total_tokens=serialized['total_tokens'],
                    cost=serialized['cost'],
                    latency_ms=serialized['latency_ms']
                )
                session.add(metric)

                # Commit all changes
                await session.commit()
                self._last_inserted_record = serialized['operation_id']
            except Exception as e:
                await session.rollback()
                raise e

    @staticmethod
    def _polars_from_db(cls,
                      agent_id: Optional[str] = None,
                      action_id: Optional[str] = None,
                      session_id: Optional[str] = None,
                      workspace: Optional[str] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      db_url: Optional[str] = None) -> "pl.DataFrame":  # noqa: F821
        """
        Query the database (using SQLAlchemy) and return results as a Polars DataFrame.
        Works with any database supported by SQLAlchemy.
        """
        try:
            import polars as pl
            from sqlalchemy import desc
        except ModuleNotFoundError:
            _logger.logger.warning("pip install aicore[all] for Polars and sql integration")
            return None
        
        try:
            session = cls.DBSession()
            
            # Build query with filters
            query = session.query(
                Session.session_id, Session.workspace, Session.agent_id,
                Message.action_id, Message.operation_id, Message.timestamp, 
                Message.system_prompt, Message.user_prompt, Message.response,
                Message.assistant_message, Message.history_messages, 
                Message.completion_args, Message.error_message,
                Metric.operation_type, Metric.provider, Metric.model, 
                Metric.success, Metric.temperature, Metric.max_tokens, 
                Metric.input_tokens, Metric.output_tokens, Metric.total_tokens,
                Metric.cost, Metric.latency_ms
            ).join(Message, Session.session_id == Message.session_id
            ).join(Metric, Message.operation_id == Metric.operation_id)
            
            # Apply filters
            if agent_id:
                query = query.filter(Session.agent_id == agent_id)
            if action_id:
                query = query.filter(Message.action_id == action_id)
            if session_id:
                query = query.filter(Session.session_id == session_id)
            if workspace:
                query = query.filter(Session.workspace == workspace)
            if start_date:
                query = query.filter(Message.timestamp >= start_date)
            if end_date:
                query = query.filter(Message.timestamp <= end_date)
                
            # Order by operation_id descending
            query = query.order_by(desc(Message.operation_id))
            results = query.all()
            session.close()
            
            if not results:
                return pl.DataFrame()
            
            # Convert to dictionary
            records = []
            for row in results:
                record = {}
                for idx, column in enumerate(query.column_descriptions):
                    record[column['name']] = row[idx]
                records.append(record)
                
            # Convert to Polars DataFrame
            return pl.from_dicts(records)
            
        except Exception as e:
            _logger.logger.warning(f"Error executing database query: {str(e)}")
            if 'session' in locals():
                session.close()
            return None
   
    @staticmethod
    async def _apolars_from_db(cls,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> "pl.DataFrame":  # noqa: F821
        """
        Query the database asynchronously (using SQLAlchemy) and return results as a Polars DataFrame.
        """
        
        try:
            import polars as pl
            from sqlalchemy import desc, select
            from sqlalchemy.ext.asyncio import AsyncSession
        except ModuleNotFoundError:
            _logger.logger.warning("pip install aicore[all] for Polars and sql integration")
            return None
        
        async with cls.aDBSession() as session:
            session :AsyncSession
            try:
                query = (
                    select(
                        Session.session_id, Session.workspace, Session.agent_id,
                        Message.action_id, Message.operation_id, Message.timestamp, 
                        Message.system_prompt, Message.user_prompt, Message.response,
                        Message.assistant_message, Message.history_messages, 
                        Message.completion_args, Message.error_message,
                        Metric.operation_type, Metric.provider, Metric.model, 
                        Metric.success, Metric.temperature, Metric.max_tokens, 
                        Metric.input_tokens, Metric.output_tokens, Metric.total_tokens,
                        Metric.cost, Metric.latency_ms
                    )
                    .join(Message, Session.session_id == Message.session_id)
                    .join(Metric, Message.operation_id == Metric.operation_id)
                )

                # Apply filters
                if agent_id:
                    query = query.where(Session.agent_id == agent_id)
                if action_id:
                    query = query.where(Message.action_id == action_id)
                if session_id:
                    query = query.where(Session.session_id == session_id)
                if workspace:
                    query = query.where(Session.workspace == workspace)
                if start_date:
                    query = query.where(Message.timestamp >= start_date)
                if end_date:
                    query = query.where(Message.timestamp <= end_date)
                
                query = query.order_by(desc(Message.operation_id))

                result = await session.execute(query)
                rows = result.all()

                if not rows:
                    return pl.DataFrame()
                
                # Convert to dictionary
                records = [dict(row._asdict()) for row in rows]
                return pl.from_dicts(records)
            except Exception as e:
                _logger.logger.error(f"Error executing database query: {str(e)}")
                return None
            
    @classmethod
    def polars_from_db(cls,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> "pl.DataFrame":  # noqa: F821
        try:
            import polars as pl
        except ModuleNotFoundError:
            _logger.logger.warning("pip install aicore[all] for Polars and sql integration")
            return None
        cls = cls()
        if cls.DBSession and cls.engine:
            return cls._polars_from_db(cls, agent_id, action_id, session_id, workspace, start_date, end_date)
        elif cls.aDBSession and cls.async_engine:            
            df = asyncio.run(cls._apolars_from_db(cls, agent_id, action_id, session_id, workspace, start_date, end_date))
            return df
        else:
            return pl.DataFrame()

    @classmethod
    def get_filter_options(cls, db_url: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Query the database to get unique filter values.
        For this schema, we provide filters for agent_id, session_id, and workspace.
        """
        try:
            from sqlalchemy import distinct
        except ModuleNotFoundError:
            _logger.logger.warning("pip install aicore for SQLAlchemy integration")
            return {}
        
        try:
            cls = cls()
            session = cls.DBSession()
            
            filter_options = {}
            
            # Get unique agent IDs
            agent_ids = session.query(distinct(Session.agent_id)).\
                        filter(Session.agent_id.isnot(None)).\
                        filter(Session.agent_id != '').\
                        order_by(Session.agent_id).all()
            filter_options['agent_id'] = [row[0] for row in agent_ids if row[0]]
            
            # Get unique session IDs
            session_ids = session.query(distinct(Session.session_id)).\
                          filter(Session.session_id.isnot(None)).\
                          filter(Session.session_id != '').\
                          order_by(Session.session_id).all()
            filter_options['session_id'] = [row[0] for row in session_ids if row[0]]
            
            # Get unique workspaces
            workspaces = session.query(distinct(Session.workspace)).\
                         filter(Session.workspace.isnot(None)).\
                         filter(Session.workspace != '').\
                         order_by(Session.workspace).all()
            filter_options['workspace'] = [row[0] for row in workspaces if row[0]]
            
            session.close()
            return filter_options
            
        except Exception as e:
            _logger.logger.error(f"Error retrieving filter options: {str(e)}")
            if 'session' in locals():
                session.close()
            return {}

    @classmethod
    def get_metrics_summary(cls,
                           agent_id: Optional[str] = None,
                           session_id: Optional[str] = None,
                           workspace: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve summary metrics from the database based on filters.
        This summary aggregates data from the metrics table.
        """
        try:
            from sqlalchemy import func
        except ModuleNotFoundError:
            _logger.logger.warning("pip install aicore for SQLAlchemy integration")
            return {}
        
        try:
            cls = cls()
            session = cls.DBSession()
            
            # Create the query with aggregates
            query = session.query(
                func.count().label('total_operations'),
                func.avg(Metric.latency_ms).label('avg_latency_ms'),
                func.sum(Metric.input_tokens).label('total_input_tokens'),
                func.sum(Metric.output_tokens).label('total_output_tokens'),
                func.sum(Metric.total_tokens).label('total_tokens'),
                func.sum(Metric.cost).label('total_cost')
            ).join(Message, Metric.operation_id == Message.operation_id
            ).join(Session, Message.session_id == Session.session_id)
            
            # Apply filters
            if agent_id:
                query = query.filter(Session.agent_id == agent_id)
            if session_id:
                query = query.filter(Session.session_id == session_id)
            if workspace:
                query = query.filter(Session.workspace == workspace)
                
            result = query.first()
            session.close()
            
            if not result:
                return {}
                
            # Convert to dictionary
            return {
                'total_operations': result.total_operations,
                'avg_latency_ms': float(result.avg_latency_ms) if result.avg_latency_ms else 0,
                'total_input_tokens': int(result.total_input_tokens) if result.total_input_tokens else 0,
                'total_output_tokens': int(result.total_output_tokens) if result.total_output_tokens else 0,
                'total_tokens': int(result.total_tokens) if result.total_tokens else 0,
                'total_cost': float(result.total_cost) if result.total_cost else 0
            }
            
        except Exception as e:
            _logger.logger.error(f"Error executing metrics query: {str(e)}")
            if 'session' in locals():
                session.close()
            return {}

if __name__ == "__main__":
    LlmOperationCollector()
    df = LlmOperationCollector.polars_from_db()
    print(df.columns)
    print(df)