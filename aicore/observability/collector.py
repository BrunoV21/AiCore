from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE, DEFAULT_ENCODING
from aicore.logger import _logger

from pydantic import BaseModel, ConfigDict, RootModel, Field, field_validator, computed_field, model_validator, model_serializer, field_serializer
from typing import Dict, Any, Optional, List, Union, Literal
from datetime import datetime, timedelta
from typing_extensions import Self
from pathlib import Path
import aiofiles
import asyncio
import orjson
import json
import ulid
import os

class LlmOperationRecord(BaseModel):
    """Data model for storing information about a single LLM operation."""
    session_id: Optional[str] = ""
    workspace: Optional[str] = ""
    agent_id: Optional[str] = ""
    action_id: Optional[str] = ""
    operation_id: str = Field(default_factory=ulid.ulid)
    timestamp: Optional[str] = ""
    operation_type: Literal["completion", "acompletion", "acompletion.tool_call"]
    provider: str
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    cached_tokens: Optional[int] = 0
    cost: Optional[float] = 0
    latency_ms: float
    error_message: Optional[str] = ""
    extras: Union[Dict[str, Any], str] = ""
    completion_args: Union[Dict[str, Any], str]
    response: Optional[Union[str, Dict, List]] = ""

    model_config = ConfigDict(
        arbitrary_types_allowed = True
    )

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

    @field_validator(*["completion_args", "extras"])
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

    @field_serializer(*["completion_args", "extras"], when_used='json')
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
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = "\n".join([str(entry) for entry in content])
                return content
        return ""

    @computed_field
    def user_prompt(self) -> Optional[str]:
        for msg in self.messages[::-1]:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = "\n".join([str(entry) for entry in content])
                return content
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
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "completion_args": json.dumps(self.completion_args, indent=4),
            "extras": json.dumps(self.extras)
        }
    

class LlmOperationCollector(RootModel):
    root: List[LlmOperationRecord] = []
    _storage_path: Optional[Union[str, Path]] = None
    _table_initialized: Optional[bool] = False
    _last_inserted_record: Optional[str] = None
    _engine: Optional[Any] = None
    _async_engine: Optional[Any] = None
    _session_factory: Optional[Any] = None
    _async_session_factory: Optional[Any] = None
    _is_sessions_initialized :set = set()

    @model_validator(mode="after")
    def init_dbsession(self) -> Self:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker            
            from aicore.observability.models import Base
            from dotenv import load_dotenv
            load_dotenv()
            
            conn_str = os.environ.get("CONNECTION_STRING")
            async_conn_str = os.environ.get("ASYNC_CONNECTION_STRING")
            
            try:
                if conn_str:
                    self._engine = create_engine(conn_str)
                    self._session_factory = sessionmaker(bind=self._engine)
                    Base.metadata.create_all(self._engine)
                    self._table_initialized = True 
                
                # Async Engine
                if async_conn_str:
                    self._async_engine = create_async_engine(async_conn_str)
                    self._async_session_factory = async_sessionmaker(
                        bind=self._async_engine, 
                        expire_on_commit=False
                    )
                
            except Exception as e:
                _logger.logger.warning(f"Database connection failed: {str(e)}")

        except ModuleNotFoundError:
           _logger.logger.warning("pip install core-for-ai[sql] for sql integration and setup ASYNC_CONNECTION_STRING env var")
        
        return self
    
    async def create_tables(self):        
        from aicore.observability.models import Base
        if not self._async_engine:
            return
        
        try:            
            from aicore.observability.models import Base
            
        except ModuleNotFoundError:
             _logger.logger.warning("pip install core-for-ai[sql] for sql integration and setup ASYNC_CONNECTION_STRING env var")
        try:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                self._table_initialized = True
        finally:
            await self._async_engine.dispose()

    @property
    def storage_path(self) -> Optional[Union[str, Path]]:
        return self._storage_path

    @storage_path.setter
    def storage_path(self, value: Union[str, Path]):
        self._storage_path = value

    def _store_to_file(self, new_record: LlmOperationRecord) -> None:
        """Store a new record by appending it to the JSON file.
        Always maintains a valid JSON array format with proper closing bracket.
        """
        # Create directory if it doesn't exist
        if not os.path.exists(os.path.dirname(self.storage_path)):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        # Case 1: File doesn't exist or is empty
        if not os.path.exists(self.storage_path) or os.path.getsize(self.storage_path) == 0:
            # Create a new file with just this record
            with open(self.storage_path, 'w', encoding=DEFAULT_ENCODING) as f:
                f.write('[\n')
                f.write(json.dumps(new_record.model_dump(), indent=4))
                f.write('\n]')
            return
        
        # Case 2: File exists with content - need to append
        with open(self.storage_path, 'r+', encoding=DEFAULT_ENCODING) as f:
            # Seek to the position right before the closing bracket
            f.seek(0, os.SEEK_END)  # Go to end of file
            pos = f.tell()          # Get current position
            
            # Go backwards until we find the closing bracket
            while pos > 0:
                pos -= 1
                f.seek(pos)
                char = f.read(1)
                if char == ']':
                    # Found the closing bracket
                    break
            
            if pos <= 0:  # Sanity check - this shouldn't happen with valid JSON
                # File might be corrupted, handle accordingly
                # For simplicity, we'll overwrite with a new file
                with open(self.storage_path, 'w', encoding=DEFAULT_ENCODING) as f_new:
                    f_new.write('[\n')
                    f_new.write(json.dumps(new_record.model_dump(), indent=4))
                    f_new.write('\n]')
                return
            
            # Truncate the file at this position to remove the closing bracket
            f.seek(pos)
            f.truncate()
            
            # Now append the new record and closing bracket
            f.write(',\n')
            f.write(json.dumps(new_record.model_dump(), indent=4))
            f.write('\n]')

    async def _a_store_to_file(self, new_record: LlmOperationRecord) -> None:
        """Async version of _store_to_file using aiofiles and orjson."""
        # Create directory if it doesn't exist
        dir_path = os.path.dirname(self.storage_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        # Prepare the record as orjson bytes (pretty)
        record_bytes = orjson.dumps(new_record.model_dump(), option=orjson.OPT_INDENT_2)

        # Case 1: File doesn't exist or is empty
        if not os.path.exists(self.storage_path) or os.path.getsize(self.storage_path) == 0:
            async with aiofiles.open(self.storage_path, 'w', encoding=DEFAULT_ENCODING) as f:
                await f.write('[\n')
                await f.write(record_bytes.decode(DEFAULT_ENCODING))
                await f.write('\n]')
            return

        # Case 2: File exists with content - need to append
        # We need to find the position of the last ']' and truncate before it
        # aiofiles does not support random access, so we must do this synchronously
        # (This is a limitation of aiofiles and file APIs)
        # So, we do the seek/truncate synchronously, then append asynchronously
        pos = None
        with open(self.storage_path, 'rb+') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            # Go backwards to find the last ']'
            for i in range(file_size - 1, -1, -1):
                f.seek(i)
                char = f.read(1)
                if char == b']':
                    pos = i
                    break
            if pos is None or pos <= 0:
                # File might be corrupted, overwrite with new file
                async with aiofiles.open(self.storage_path, 'w', encoding=DEFAULT_ENCODING) as f_new:
                    await f_new.write('[\n')
                    await f_new.write(record_bytes.decode(DEFAULT_ENCODING))
                    await f_new.write('\n]')
                return
            f.seek(pos)
            f.truncate()
        # Now append the new record and closing bracket asynchronously
        async with aiofiles.open(self.storage_path, 'a', encoding=DEFAULT_ENCODING) as f:
            await f.write(',\n')
            await f.write(record_bytes.decode(DEFAULT_ENCODING))
            await f.write('\n]')

    def read_all_records(self) -> "LlmOperationCollector":
        """Read all records from the file.
        The file is always maintained in valid JSON format.
        """
        if not os.path.exists(self.storage_path) or os.path.getsize(self.storage_path) == 0:
            return LlmOperationCollector.model_construct(root=[])
        
        # File is always in valid JSON format, so we can read directly
        with open(self.storage_path, 'r', encoding=DEFAULT_ENCODING) as f:
            try:
                data = json.loads(f.read())
                records = LlmOperationCollector.model_construct(
                    root=[LlmOperationRecord(**kwargs) for kwargs in data]
                )
                return records
            except json.JSONDecodeError:
                # Handle potential corrupted file
                return LlmOperationCollector.model_construct(root=[])

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
        cached_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None
    ) -> LlmOperationRecord:
        # Clean request args
        cleaned_args = self._clean_completion_args(completion_args)

        if not isinstance(response, (str, dict, list)) and response is not None:
            return None
        
        # Build a record
        record = LlmOperationRecord(
            session_id=session_id,
            agent_id=agent_id,
            action_id=action_id,
            workspace=workspace,
            provider=provider,
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens if not cached_tokens else output_tokens + cached_tokens,
            cached_tokens=cached_tokens,
            cost=cost,
            latency_ms=latency_ms or 0,
            error_message=error_message,
            completion_args=cleaned_args,
            response=response,
            extras=extras or {}
        )
        if self.storage_path:
            self._store_to_file(record)
        
        self.root.append(record)

        return record

    async def _a_handle_record(
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
        cached_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None
    ) -> LlmOperationRecord:
        # Clean request args
        cleaned_args = self._clean_completion_args(completion_args)

        if not isinstance(response, (str, dict, list)) and response is not None:
            return None

        # Build a record
        record = LlmOperationRecord(
            session_id=session_id,
            agent_id=agent_id,
            action_id=action_id,
            workspace=workspace,
            provider=provider,
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens if not cached_tokens else output_tokens + cached_tokens,
            cached_tokens=cached_tokens,
            cost=cost,
            latency_ms=latency_ms or 0,
            error_message=error_message,
            completion_args=cleaned_args,
            response=response,
            extras=extras or {}
        )
        if self.storage_path:
            await self._a_store_to_file(record)

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
        cached_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extras: Optional[str] = None
    ) -> LlmOperationRecord:
        # Create record
        record = self._handle_record(
            completion_args, operation_type, provider, response, 
            session_id, workspace, agent_id, action_id, 
            input_tokens, output_tokens, cached_tokens, cost, latency_ms, error_message, extras
        )
        
        if self._engine and self._session_factory and record:
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
        cached_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extras: Optional[str] = None
    ) -> LlmOperationRecord:
        # Create record asynchronously
        record = await self._a_handle_record(
            completion_args, operation_type, provider, response,
            session_id, workspace, agent_id, action_id,
            input_tokens, output_tokens, cached_tokens, cost, latency_ms, error_message, extras
        )

        if self._async_engine and self._async_session_factory and record:
            if not self._table_initialized:
                await self.create_tables()
            try:
                await self._a_insert_record_to_db(record)
            except Exception as e:
                _logger.logger.error(f"Error inserting record to DB: {str(e)}")

        return record
    
    def _insert_record_to_db(self, record: LlmOperationRecord) -> None:
        """Insert a single LLM operation record into the database using SQLAlchemy."""
        try:
            from aicore.observability.models import Session, Message, Metric
        except ModuleNotFoundError:
             _logger.logger.warning("pip install core-for-ai[sql] for sql integration and setup ASYNC_CONNECTION_STRING env var")
        
        if not self._session_factory:
            if self._async_session_factory:
                _logger.logger.warning("You have configured an async connection to a db but are trying to establish a sync one. Pass CONNECTION_STRING env var.")
            return
            
        serialized = record.serialize_model()
        
        # Use context manager for session handling
        with self._session_factory() as session:
            try:
                # Check if session exists, create if it doesn't
                db_session_query = session.query(Session).filter_by(session_id=serialized['session_id'])
                db_session = list(db_session_query.all())  # Force fetch all results
                
                if not db_session:
                    db_session = Session(
                        session_id=serialized['session_id'],
                        workspace=serialized['workspace'],
                        agent_id=serialized['agent_id']
                    )
                    session.add(db_session)
                    session.flush()  # Flush changes to DB but don't commit yet
                else:
                    db_session = db_session[0]  # Get first result
                
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
                    cached_tokens=serialized['cached_tokens'],
                    total_tokens=serialized['total_tokens'],
                    cost=serialized['cost'],
                    latency_ms=serialized['latency_ms'],
                    extras=serialized['extras']
                )
                session.add(metric)
                
                # Commit all changes
                session.commit()
                self._last_inserted_record = serialized['operation_id']
            except Exception as e:
                session.rollback()
                raise e

    async def _a_insert_record_to_db(self, record: LlmOperationRecord) -> None:
        """Insert a single LLM operation record into the database asynchronously."""
        if not self._async_session_factory:
            if self._session_factory:
                _logger.logger.warning("You have configured a sync connection to a db but are trying to establish an async one. Pass ASYNC_CONNECTION_STRING env var.")
            return

        serialized = record.serialize_model()
        
        try:
            from sqlalchemy.future import select
            from aicore.observability.models import Session, Message, Metric
            
            # First with block: Handle session creation
            async with self._async_session_factory() as session:
                try:
                    # Check if session exists, create if it doesn't
                    if serialized['session_id'] not in self._is_sessions_initialized:
                        # Check if any row exists
                        db_session = await session.scalar(
                            select(1).where(Session.session_id == serialized['session_id'])
                        )
                        result = db_session is not None

                        if not result:
                            db_session = Session(
                                session_id=serialized['session_id'],
                                workspace=serialized['workspace'],
                                agent_id=serialized['agent_id']
                            )
                            session.add(db_session)
                            await session.commit()
                            self._is_sessions_initialized.add(serialized['session_id'])
                except Exception as e:
                    await session.rollback()
                    raise e

            # Second with block: Handle message insertion
            async with self._async_session_factory() as session:
                try:
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
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    raise e

            # Third with block: Handle metrics insertion
            async with self._async_session_factory() as session:
                try:
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
                        cached_tokens=serialized['cached_tokens'],
                        total_tokens=serialized['total_tokens'],
                        cost=serialized['cost'],
                        latency_ms=serialized['latency_ms'],
                        extras=serialized['extras']
                    )
                    session.add(metric)
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    raise e
            
            # Set the last inserted record after all operations succeed
            self._last_inserted_record = serialized['operation_id']
            
        finally:
            await self._async_engine.dispose()

    @classmethod
    def polars_from_db(cls,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> "pl.DataFrame":  # noqa: F821
        """
        Query the database and return results as a Polars DataFrame.
        Works with any database supported by SQLAlchemy.
        
        Defaults:
            - start_date: Midnight of the previous day
            - end_date: Now (current time)
        """
        # Set default start_date to midnight of the previous day
        if start_date is None:
            yesterday = datetime.now() - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        # Set default end_date to now (optional)
        if end_date is None:
            end_date = datetime.now().isoformat()

        instance = cls()
        
        if instance._session_factory and instance._engine:
            return instance._polars_from_db(
                agent_id, action_id, session_id, workspace, start_date, end_date
            )
        elif instance._async_session_factory and instance._async_engine:
            coro = instance._apolars_from_db(agent_id, action_id, session_id, workspace, start_date, end_date)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop: safe to use asyncio.run
                return asyncio.run(coro)
            else:
                # Already inside a running loop — use `ensure_future` or `create_task`
                future = asyncio.ensure_future(coro)
                return asyncio.get_event_loop().run_until_complete(future)
        else:
            try:
                import polars as pl
                return pl.DataFrame()
            except ModuleNotFoundError:
                _logger.logger.warning("pip install core-for-ai[all] for Polars and sql integration")
                return None

    def _polars_from_db(self,
                    agent_id: Optional[str] = None,
                    action_id: Optional[str] = None,
                    session_id: Optional[str] = None,
                    workspace: Optional[str] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> "pl.DataFrame":  # noqa: F821
        """
        Query the database (using SQLAlchemy) and return results as a Polars DataFrame.
        Works with any database supported by SQLAlchemy.
        """
        try:
            import polars as pl
            from sqlalchemy import desc
            from aicore.observability.models import Session, Message, Metric
        except ModuleNotFoundError:
            _logger.logger.warning("pip install core-for-ai[all] for Polars and sql integration")
            return None
        
        with self._session_factory() as session:
            try:
                # Build query with filters
                query = session.query(
                    Session.session_id, Session.workspace, Session.agent_id,
                    Message.action_id, Message.operation_id, Message.timestamp, 
                    Message.system_prompt, Message.user_prompt, Message.response,
                    Message.assistant_message, Message.history_messages, 
                    Message.completion_args, Message.error_message,
                    Metric.operation_type, Metric.provider, Metric.model, 
                    Metric.success, Metric.temperature, Metric.max_tokens, 
                    Metric.input_tokens, Metric.output_tokens, Metric.cached_tokens, Metric.total_tokens,
                    Metric.cost, Metric.latency_ms, Metric.extras
                ).join(
                    Message, Session.session_id == Message.session_id
                ).join(
                    Metric, Message.operation_id == Metric.operation_id
                ).filter(
                    Message.timestamp >= start_date,
                    Message.timestamp <= end_date
                )
                
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
                
                # Force immediate consumption of all results to prevent "Connection is busy" errors
                results = list(query.all())
                
                if not results:
                    return pl.DataFrame()
                
                # Convert to dictionary
                records = []
                for row in results:
                    record = {}
                    for idx, column in enumerate(query.column_descriptions):
                        record[column['name']] = row[idx]
                    records.append(record)
                    
                # Ensure session is clean before returning
                session.commit()
                
                # Convert to Polars DataFrame
                return pl.from_dicts(records)
                
            except Exception as e:
                _logger.logger.warning(f"collector.py:640 Error executing database query: {str(e)}")
                session.rollback()  # Explicitly rollback on error
                return pl.DataFrame()
   
    async def _apolars_from_db(self,
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
            from aicore.observability.models import Session, Message, Metric
        except ModuleNotFoundError:
            _logger.logger.warning("pip install core-for-ai[all] for Polars and sql integration")
            return None
        
        async with self._async_session_factory() as session:
            try:
                session = self._async_session_factory()
                query = (
                    select(
                        Session.session_id, Session.workspace, Session.agent_id,
                        Message.action_id, Message.operation_id, Message.timestamp, 
                        Message.system_prompt, Message.user_prompt, Message.response,
                        Message.assistant_message, Message.history_messages, 
                        Message.completion_args, Message.error_message,
                        Metric.operation_type, Metric.provider, Metric.model, 
                        Metric.success, Metric.temperature, Metric.max_tokens, 
                        Metric.input_tokens, Metric.output_tokens, Metric.cached_tokens, Metric.total_tokens,
                        Metric.cost, Metric.latency_ms, Metric.extras
                    )
                    .join(Message, Session.session_id == Message.session_id)
                    .join(Metric, Message.operation_id == Metric.operation_id)
                    .filter(
                        Message.timestamp >= start_date,
                        Message.timestamp <= end_date
                    )
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
                
                query = query.order_by(desc(Message.operation_id))

                # Execute query and immediately consume all results
                result = await session.execute(query)
                rows = result.fetchall()  # eager fetch
                
                # Explicitly commit to ensure connection is cleared
                await session.commit()

                if not rows:
                    return pl.DataFrame()
                
                # Convert to dictionary
                records = [dict(row._asdict()) for row in rows]
                return pl.from_dicts(records)
            except Exception as e:
                _logger.logger.error(f"Error executing database query: {str(e)}")
                await session.rollback()  # Explicitly rollback on error
                return pl.DataFrame()            
            
            finally:
                await self._async_engine.dispose()

if __name__ == "__main__":
    LlmOperationCollector()
    df = LlmOperationCollector.polars_from_db()
    print(df.columns)
    print(df)