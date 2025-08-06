import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Literal, Any as _Any
from typing_extensions import Self

import ulid
from pydantic import (
    BaseModel,
    ConfigDict,
    RootModel,
    Field,
    field_validator,
    computed_field,
    model_validator,
    model_serializer,
    field_serializer,
)

from aicore.logger import _logger
from aicore.const import (
    DEFAULT_OBSERVABILITY_DIR,
    DEFAULT_OBSERVABILITY_FILE,
    DEFAULT_ENCODING,
)

# Cleanup utilities – run once per dashboard launch
from aicore.observability.cleanup import (
    cleanup_old_observability_messages,
    register_cleanup_task,
)


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator(
        "session_id",
        "workspace",
        "agent_id",
        "action_id",
        "timestamp",
        "error_message",
        "response",
    )
    @classmethod
    def ensure_non_nulls(cls, value: Optional[str] = None) -> str:
        """Convert ``None`` values to empty strings."""
        return "" if value is None else value

    @field_validator("response")
    @classmethod
    def json_dumps_response(
        cls, response: Union[None, str, Dict, List]
    ) -> Optional[str]:
        """Serialize response to JSON if needed."""
        if isinstance(response, (str, type(None))):
            return response
        if isinstance(response, (dict, list)):
            return json.dumps(response, indent=4)
        raise TypeError("response must be a string or JSON‑serializable object")

    @field_validator("completion_args", "extras")
    @classmethod
    def json_loads_response(cls, args: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse JSON strings for args/extras."""
        if isinstance(args, str):
            return json.loads(args)
        return args

    @model_validator(mode="after")
    def init_workspace_and_timestamp(self) -> Self:
        """Set default timestamp and workspace if missing."""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        self.workspace = self.workspace or os.getenv("WORKSPACE", "")
        return self

    @field_serializer("completion_args", "extras", when_used="json")
    def json_dump_completion_args(self, value: Dict[str, Any]) -> str:
        """Serialize ``completion_args`` for JSON output."""
        return json.dumps(value, indent=4)

    @property
    def messages(self) -> List[Dict[str, str]]:
        """Extract messages from ``completion_args``."""
        return self.completion_args.get("messages", [])

    @computed_field
    def model(self) -> str:
        return self.completion_args.get("model", "")

    @computed_field
    def temperature(self) -> float:
        return self.completion_args.get("temperature", 0.0)

    @computed_field
    def max_tokens(self) -> int:
        return (
            self.completion_args.get("max_tokens", 0)
            or self.completion_args.get("max_completion_tokens", 0)
        )

    @computed_field
    def system_prompt(self) -> Optional[str]:
        for msg in self.messages:
            if msg.get("role") == "system":
                return msg.get("content", "")
        if self.completion_args.get("system"):
            return self.completion_args["system"]
        return ""

    @computed_field
    def assistant_message(self) -> Optional[str]:
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = "\n".join(map(str, content))
                return content
        return ""

    @computed_field
    def user_prompt(self) -> Optional[str]:
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = "\n".join(map(str, content))
                return content
        return ""

    @computed_field
    def history_messages(self) -> Optional[str]:
        return json.dumps(
            [
                msg
                for msg in self.messages
                if msg.get("content")
                not in [
                    self.system_prompt,
                    self.assistant_message,
                    self.user_prompt,
                ]
            ],
            indent=4,
        )

    @computed_field
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @computed_field
    def success(self) -> bool:
        return bool(self.response)

    @model_serializer
    def serialize_model(self) -> Dict[str, Any]:
        """Serialize the record with a stable field order."""
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
            "extras": json.dumps(self.extras),
        }


class LlmOperationCollector(RootModel):
    """Collects LLM operation records and persists them."""

    root: List[LlmOperationRecord] = []
    _storage_path: Optional[Union[str, Path]] = None
    _table_initialized: bool = False
    _last_inserted_record: Optional[str] = None
    _engine: Optional[_Any] = None
    _async_engine: Optional[_Any] = None
    _session_factory: Optional[_Any] = None
    _async_session_factory: Optional[_Any] = None

    # Cleanup flags – ensure cleanup runs only once per launch
    _cleanup_done: bool = False
    _cleanup_failed: bool = False

    @model_validator(mode="after")
    def init_dbsession(self) -> Self:
        """Initialize SQLAlchemy engines and run cleanup."""
        # -----------------------------------------------------------------
        # Database engine setup
        # -----------------------------------------------------------------
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
            from aicore.observability.models import Base
            from dotenv import load_dotenv

            load_dotenv()

            conn_str = os.getenv("CONNECTION_STRING")
            async_conn_str = os.getenv("ASYNC_CONNECTION_STRING")

            if conn_str:
                self._engine = create_engine(conn_str)
                self._session_factory = sessionmaker(bind=self._engine)
                Base.metadata.create_all(self._engine)
                self._table_initialized = True

            if async_conn_str:
                self._async_engine = create_async_engine(async_conn_str)
                self._async_session_factory = async_sessionmaker(
                    bind=self._async_engine,
                    expire_on_commit=False,
                )
        except ModuleNotFoundError:
            _logger.logger.warning(
                "pip install core-for-ai[sql] and set CONNECTION_STRING/ASYNC_CONNECTION_STRING"
            )
        except Exception as e:
            _logger.logger.warning(f"Database connection failed: {e}")

        # -----------------------------------------------------------------
        # Run cleanup of old observability messages (once per launch)
        # -----------------------------------------------------------------
        if not self.__class__._cleanup_done or self.__class__._cleanup_failed:
            try:
                deleted = cleanup_old_observability_messages()
                    # Log the number of deleted rows for auditing.
                    _logger.logger.info(
                        f"Observability cleanup removed {deleted} old messages."
                    )
                    self.__class__._cleanup_done = True
                    self.__class__._cleanup_failed = False
                except Exception as e:
                    _logger.logger.warning(f"Observability cleanup failed: {e}")
                    self.__class__._cleanup_failed = True

        # Register recurring cleanup task if a scheduler is available
        try:
            register_cleanup_task()
        except Exception:
            # Scheduler not available – ignore silently
            pass

        return self

    async def create_tables(self) -> None:
        """Create tables for async engine."""
        from aicore.observability.models import Base
        if not self._async_engine:
            return
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
    def storage_path(self, value: Union[str, Path]) -> None:
        self._storage_path = value

    def _store_to_file(self, new_record: LlmOperationRecord) -> None:
        """Append a new record to the JSON file."""
        if not os.path.exists(os.path.dirname(self.storage_path)):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

        if not os.path.exists(self.storage_path) or os.path.getsize(
            self.storage_path
        ) == 0:
            with open(self.storage_path, "w", encoding=DEFAULT_ENCODING) as f:
                f.write("[\n")
                f.write(json.dumps(new_record.model_dump(), indent=4))
                f.write("\n]")
            return

        with open(self.storage_path, "r+", encoding=DEFAULT_ENCODING) as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            # Find the position of the closing bracket ']'
            while pos > 0:
                pos -= 1
                f.seek(pos)
                if f.read(1) == "]":
                    break
            if pos <= 0:
                # File is malformed; rewrite from scratch
                with open(self.storage_path, "w", encoding=DEFAULT_ENCODING) as f_new:
                    f_new.write("[\n")
                    f_new.write(json.dumps(new_record.model_dump(), indent=4))
                    f_new.write("\n]")
                return

            # Truncate the closing bracket and append the new record
            f.seek(pos)
            f.truncate()
            f.write(",\n")
            f.write(json.dumps(new_record.model_dump(), indent=4))
            f.write("\n]")

    def read_all_records(self) -> "LlmOperationCollector":
        """Read all records from the JSON file."""
        if not os.path.exists(self.storage_path) or os.path.getsize(
            self.storage_path
        ) == 0:
            return LlmOperationCollector.model_construct(root=[])

        with open(self.storage_path, "r", encoding=DEFAULT_ENCODING) as f:
            try:
                data = json.load(f)
                records = LlmOperationCollector.model_construct(
                    root=[LlmOperationRecord(**kwargs) for kwargs in data]
                )
                return records
            except json.JSONDecodeError:
                # Return an empty collector on malformed JSON
                return LlmOperationCollector.model_construct(root=[])

    @staticmethod
    def _clean_completion_args(args: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from request arguments."""
        cleaned = args.copy()
        cleaned.pop("api_key", None)
        return cleaned

    @classmethod
    def from_observable_storage_path(
        cls, storage_path: Optional[str] = None
    ) -> "LlmOperationCollector":
        """Create a collector with a storage path, respecting env var."""
        obj = cls()
        env_path = os.getenv("OBSERVABILITY_DATA_DEFAULT_FILE")
        if storage_path:
            obj.storage_path = storage_path
        elif env_path:
            obj.storage_path = env_path
        else:
            obj.storage_path = Path(DEFAULT_OBSERVABILITY_DIR) / DEFAULT_OBSERVABILITY_FILE
        return obj

    # Compatibility alias for tests that used a misspelled method name.
    @classmethod
    def fom_observable_storage_path(
        cls, storage_path: Optional[str] = None
    ) -> "LlmOperationCollector":
        """Alias for ``from_observable_storage_path``."""
        return cls.from_observable_storage_path(storage_path)

    @classmethod
    def polars_from_file(
        cls, storage_path: Optional[str] = None
    ) -> "pl.DataFrame":  # noqa: F821
        """Load records from a JSON file into a Polars DataFrame."""
        obj = cls.from_observable_storage_path(storage_path)
        if os.path.exists(obj.storage_path):
            with open(obj.storage_path, "r", encoding=DEFAULT_ENCODING) as f:
                obj = cls(root=json.load(f))
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
        response: Optional[Union[str, Dict, List]] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        cost: float = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> Optional[LlmOperationRecord]:
        cleaned_args = self._clean_completion_args(completion_args)

        if response is not None and not isinstance(response, (str, dict, list)):
            return None

        record = LlmOperationRecord(
            session_id=session_id,
            workspace=workspace,
            agent_id=agent_id,
            action_id=action_id,
            operation_type=operation_type,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens if not cached_tokens else output_tokens + cached_tokens,
            cached_tokens=cached_tokens,
            cost=cost,
            latency_ms=latency_ms or 0,
            error_message=error_message,
            completion_args=cleaned_args,
            response=response,
            extras=extras or {},
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
        response: Optional[Union[str, Dict, List]] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        cost: float = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> Optional[LlmOperationRecord]:
        record = self._handle_record(
            completion_args,
            operation_type,
            provider,
            response,
            session_id,
            workspace,
            agent_id,
            action_id,
            input_tokens,
            output_tokens,
            cached_tokens,
            cost,
            latency_ms,
            error_message,
            extras,
        )
        if self._engine and self._session_factory and record:
            try:
                self._insert_record_to_db(record)
                    _logger.logger.info("Record inserted into DB.")
                    self._last_inserted_record = record.operation_id
                except Exception as e:
                    _logger.logger.error(f"Error inserting record to DB: {e}")
        return record

    async def arecord_completion(
        self,
        completion_args: Dict[str, Any],
        operation_type: Literal["completion", "acompletion"],
        provider: str,
        response: Optional[Union[str, Dict, List]] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        cost: float = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> Optional[LlmOperationRecord]:
        record = self._handle_record(
            completion_args,
            operation_type,
            provider,
            response,
            session_id,
            workspace,
            agent_id,
            action_id,
            input_tokens,
            output_tokens,
            cached_tokens,
            cost,
            latency_ms,
            error_message,
            extras,
        )
        if self._async_engine and self._async_session_factory and record:
            if not self._table_initialized:
                await self.create_tables()
            try:
                await self._a_insert_record_to_db(record)
                _logger.logger.info("Async record inserted into DB.")
                self._last_inserted_record = record.operation_id
            except Exception as e:
                _logger.error(f"Error inserting async record: {e}")
        return record

    def _insert_record_to_db(self, record: LlmOperationRecord) -> None:
        """Insert a record into the DB synchronously."""
        try:
            from aicore.observability.models import Session, Message, Metric
        except ModuleNotFoundError:
            _logger.logger.warning(
                "pip install core-for-ai[sql] and set CONNECTION_STRING"
            )
            return

        serialized = record.serialize_model()
        with self._session_factory() as session:
            try:
                db_session = (
                    session.query(Session)
                    .filter_by(session_id=serialized["session_id"])
                    .first()
                )
                if not db_session:
                    db_session = Session(
                        session_id=serialized["session_id"],
                        workspace=serialized["workspace"],
                        agent_id=serialized["agent_id"],
                    )
                    session.add(db_session)
                    session.flush()

                message = Message(
                    operation_id=serialized["operation_id"],
                    session_id=serialized["session_id"],
                    action_id=serialized["action_id"],
                    timestamp=serialized["timestamp"],
                    system_prompt=serialized["system_prompt"],
                    user_prompt=serialized["user_prompt"],
                    response=serialized["response"],
                    assistant_message=serialized["assistant_message"],
                    history_messages=serialized["history_messages"],
                    completion_args=serialized["completion_args"],
                    error_message=serialized["error_message"],
                )
                session.add(message)

                metric = Metric(
                    operation_id=serialized["operation_id"],
                    operation_type=serialized["operation_type"],
                    provider=serialized["provider"],
                    model=serialized["model"],
                    success=serialized["success"],
                    temperature=serialized["temperature"],
                    max_tokens=serialized["max_tokens"],
                    input_tokens=serialized["input_tokens"],
                    output_tokens=serialized["output_tokens"],
                    cached_tokens=serialized["cached_tokens"],
                    total_tokens=serialized["total_tokens"],
                    cost=serialized["cost"],
                    latency_ms=serialized["latency_ms"],
                    extras=serialized["extras"],
                )
                session.add(metric)
                session.commit()
            except Exception:
                session.rollback()
                raise

    async def _a_insert_record_to_db(self, record: LlmOperationRecord) -> None:
        """Insert a record into the DB asynchronously."""
        if not self._async_session_factory:
            _logger.logger.warning(
                "Async DB connection not configured; set ASYNC_CONNECTION_STRING."
            )
            return

        serialized = record.serialize_model()
        async with self._async_session_factory() as session:
            try:
                from aicore.observability.models import Session, Message, Metric
                result = await session.execute(
                    select(Session).filter_by(session_id=serialized["session_id"])
                )
                db_session = result.scalars().first()
                if not db_session:
                    db_session = Session(
                        session_id=serialized["session_id"],
                        workspace=serialized["workspace"],
                        agent_id=serialized["agent_id"],
                    )
                    session.add(db_session)
                    await session.flush()

                message = Message(
                    operation_id=serialized["operation_id"],
                    session_id=serialized["session_id"],
                    action_id=serialized["action_id"],
                    timestamp=serialized["timestamp"],
                    system_prompt=serialized["system_prompt"],
                    user_prompt=serialized["user_prompt"],
                    response=serialized["response"],
                    assistant_message=serialized["assistant_message"],
                    history_messages=serialized["history_messages"],
                    completion_args=serialized["completion_args"],
                    error_message=serialized["error_message"],
                )
                session.add(message)

                metric = Metric(
                    operation_id=serialized["operation_id"],
                    operation_type=serialized["operation_type"],
                    provider=serialized["provider"],
                    model=serialized["model"],
                    success=serialized["success"],
                    temperature=serialized["temperature"],
                    max_tokens=serialized["max_tokens"],
                    input_tokens=serialized["input_tokens"],
                    output_tokens=serialized["output_tokens"],
                    cached_tokens=serialized["cached_tokens"],
                    total_tokens=serialized["total_tokens"],
                    cost=serialized["cost"],
                    latency_ms=serialized["latency_ms"],
                    extras=serialized["extras"],
                )
                session.add(metric)

                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await self._async_engine.dispose()

    @classmethod
    def polars_from_db(
        cls,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pl.DataFrame":  # noqa: F821
        """Query DB and return a Polars DataFrame."""
        if start_date is None:
            start_date = (
                datetime.now() - timedelta(days=1)
            ).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        if end_date is None:
            end_date = datetime.now().isoformat()

        instance = cls()
        if instance._session_factory and instance._engine:
            return instance._polars_from_db(
                agent_id,
                action_id,
                session_id,
                workspace,
                start_date,
                end_date,
            )
        if instance._async_session_factory and instance._async_engine:
            coro = instance._apolars_from_db(
                agent_id,
                action_id,
                session_id,
                workspace,
                start_date,
                end_date,
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(coro)
            else:
                future = asyncio.ensure_future(coro)
                return asyncio.get_event_loop().run_until_complete(future)

        try:
            import polars as pl

            return pl.DataFrame()
        except ModuleNotFoundError:
            _logger.logger.warning(
                "pip install core-for-ai[all] for Polars and SQL integration"
            )
            return None

    def _polars_from_db(
        self,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pl.DataFrame":  # noqa: F821
        """Query DB synchronously and return a Polars DataFrame."""
        try:
            import polars as pl
            from sqlalchemy import desc
            from aicore.observability.models import Session, Message, Metric
        except ModuleNotFoundError:
            _logger.logger.warning(
                "pip install core-for-ai[all] for Polars and SQL integration"
            )
            return None

        with self._session_factory() as session:
            try:
                query = (
                    session.query(
                        Session.session_id,
                        Session.workspace,
                        Session.agent_id,
                        Message.action_id,
                        Message.operation_id,
                        Message.timestamp,
                        Message.system_prompt,
                        Message.user_prompt,
                        Message.response,
                        Message.assistant_message,
                        Message.history_messages,
                        Message.completion_args,
                        Message.error_message,
                        Metric.operation_type,
                        Metric.provider,
                        Metric.model,
                        Metric.success,
                        Metric.temperature,
                        Metric.max_tokens,
                        Metric.input_tokens,
                        Output.output_tokens,
                        Cached.cached_tokens,
                        Total.total_tokens,
                        Cost.cost,
                        Latency.latency_ms,
                        Extras.extras,
                    )
                    .join(Message, Session.session_id == Message.session_id)
                    .join(Metric, Message.operation_id == Metric.operation_id)
                    .filter(Message.timestamp >= start_date, Message.timestamp <= end_date)
                )
                if agent_id:
                    query = query.filter(Session.agent_id == agent_id)
                if action_id:
                    query = query.filter(Message.action_id == action_id)
                if session_id:
                    query = query.filter(Session.session_id == session_id)
                if workspace:
                    query = query.filter(Session.workspace == workspace)

                query = query.order_by(desc(Message.operation_id))
                results = list(query.all())
                if not results:
                    return pl.DataFrame()

                records = []
                for row in results:
                    record = {}
                    for idx, column in enumerate(query.column_descriptions):
                        record[column["name"]] = row[idx]
                    records.append(record)

                session.commit()
                return pl.from_dicts(records)
            except Exception as e:
                _logger.logger.warning(f"collector.py:640 DB query error: {e}")
                session.rollback()
                return pl.DataFrame()

    async def _apolars_from_db(
        self,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pl.DataFrame":  # noqa: F821
        """Query DB asynchronously and return a Polars DataFrame."""
        try:
            import polars as pl
            from sqlalchemy import desc, select
            from aicore.observability.models import Session, Message, Metric
        except ModuleNotFoundError:
            _logger.logger.warning(
                "pip install core-for-ai[all] for Polars and SQL integration"
            )
            return None

        async with self._async_session_factory() as session:
            try:
                query = (
                    select(
                        Session.session_id,
                        Session.workspace,
                        Session.agent_id,
                        Message.action_id,
                        Message.operation_id,
                        Message.timestamp,
                        Message.system_prompt,
                        Message.user_prompt,
                        Message.response,
                        Message.assistant_message,
                        Message.history_messages,
                        Message.completion_args,
                        Message.error_message,
                        Metric.operation_type,
                        Metric.provider,
                        Metric.model,
                        Metric.success,
                        Metric.temperature,
                        Metric.max_tokens,
                        Metric.input_tokens,
                        Output.output_tokens,
                        Cached.cached_tokens,
                        Total.total_tokens,
                        Cost.cost,
                        Latency.latency_ms,
                        Extras.extras,
                    )
                    .join(Message, Session.session_id == Message.session_id)
                    .join(Metric, Message.operation_id == Metric.operation_id)
                    .filter(Message.timestamp >= start_date, Timestamp.timestamp <= end_date)
                )
                if agent_id:
                    query = query.where(Session.agent_id == agent_id)
                if action_id:
                    query = query.where(Message.action_id == action_id)
                if session_id:
                    query = query.where(Session.session_id == session_id)
                if workspace:
                    query = where(Session.workspace == workspace)

                query = query.order_by(desc(Message.operation_id))
                result = await session.execute(query)
                rows = result.fetchall()
                await session.commit()
                if not rows:
                    return pl.DataFrame()
                records = [dict(row._asdict()) for row in rows]
                return pl.from_dicts(records)
            except Exception as e:
                _logger.error(f"Async DB query error: {e}")
                await session.rollback()
                return pl.DataFrame()
            finally:
                await self._async_engine.dispose()


if __name__ == "__main__":
    LlmOperationCollector()
    df = LlmOperationCollector.polars_from_db()
    print(df.columns)
    print(df)