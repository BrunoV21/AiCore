import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Literal, Self

import ulid
from pydantic import BaseModel, RootModel, Field, field_validator, computed_field, model_validator, model_serializer, field_serializer

from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE, DEFAULT_ENCODING

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
        return self.completion_args.get("temperature", "")

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
    _db_conn: Optional["psycopg2.extensions.connection"] = None  # noqa: F821

    @model_validator(mode="after")
    def init_db_conn(self) -> Self:
        try:
            import psycopg2
            import psycopg2.extensions
            from dotenv import load_dotenv
            load_dotenv()
            conn_str = os.environ.get("PG_CONNECTION_STRING")
            if conn_str:
                try:
                    self.db_conn = psycopg2.connect(conn_str)
                    self._init_db_tables()  # use the new multi-table initializer
                except Exception as e:
                    print(f"Database connection failed: {str(e)}")
                    self._db_conn = None
        except ModuleNotFoundError:
            raise ModuleNotFoundError("pip install aicore[pg] for postgress integration and setup PG_CONNECTION_STRING env var")
        return self

    @property
    def storage_path(self) -> Optional[Union[str, Path]]:
        return self._storage_path

    @property
    def db_conn(self) -> Optional["psycopg2.extensions.connection"]:  # noqa: F821
        return self._db_conn

    @db_conn.setter
    def db_conn(self, connection: Optional["psycopg2.extensions.connection"]):  # noqa: F821
        self._db_conn = connection

    @storage_path.setter
    def storage_path(self, value: Union[str, Path]):
        self._storage_path = value

    def _store_to_file(self, new_record: LlmOperationRecord) -> None:
        if not os.path.exists(self.storage_path):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            records = LlmOperationCollector()
        else:
            with open(self.storage_path, 'r', encoding=DEFAULT_ENCODING) as f:
                records = LlmOperationCollector(root=json.loads(f.read()))
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
            return pl.from_dicts(obj.model_dump())
        except ModuleNotFoundError:
            print("pip install -r requirements-dashboard.txt")
            return None

    def record_completion(
        self,
        completion_args: Dict[str, Any],
        operation_type: Literal["completion", "acompletion"],
        provider: str,
        response: Optional[Union[str, Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        agent_id: Optional[str] = None,
        action_id :Optional[str]=None,
        input_tokens: Optional[int] = 0,
        output_tokens: Optional[int] = 0,
        cost: Optional[float] = 0,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> LlmOperationRecord:
        # Clean request args to remove potentially sensitive or large objects
        cleaned_args = self._clean_completion_args(completion_args)

        # Build a record (assumes LlmOperationRecord includes these fields)
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

        if self.db_conn:
            try:
                self._insert_record_to_db(record)
            except Exception as e:
                # In a production system, proper logging should be done here.
                print(f"Error inserting record to DB: {str(e)}")

        return record

    def _init_db_tables(self) -> None:
        """
        Initialize three tables: sessions, messages, and metrics.
        """
        sessions_table_sql = """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR PRIMARY KEY,
            workspace VARCHAR,
            agent_id VARCHAR
        );
        """
        messages_table_sql = """
        CREATE TABLE IF NOT EXISTS messages (
            operation_id VARCHAR PRIMARY KEY,
            session_id VARCHAR REFERENCES sessions(session_id),
            action_id VARCHAR,
            timestamp VARCHAR,
            system_prompt TEXT,
            user_prompt TEXT,
            response TEXT,
            assistant_message TEXT,
            history_messages TEXT,
            completion_args TEXT,
            error_messages TEXT
        );
        """
        metrics_table_sql = """
        CREATE TABLE IF NOT EXISTS metrics (
            operation_id VARCHAR PRIMARY KEY REFERENCES messages(operation_id),
            operation_type VARCHAR,
            provider VARCHAR,
            model VARCHAR,
            success BOOL,
            temperature VARCHAR,
            max_tokens INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            cost FLOAT,
            latency_ms FLOAT
        );
        """
        cur = self.db_conn.cursor()
        cur.execute(sessions_table_sql)
        cur.execute(messages_table_sql)
        cur.execute(metrics_table_sql)
        self.db_conn.commit()
        cur.close()
        self._table_initialized = True

    def _insert_record_to_db(self, record: LlmOperationRecord) -> None:
        """
        Insert a single LLM operation record into the three PostgreSQL tables.
        """
        # Insert session (if not already present)
        insert_session_sql = """
        INSERT INTO sessions (session_id, workspace, agent_id)
        VALUES (%(session_id)s, %(workspace)s, %(agent_id)s)
        ON CONFLICT (session_id) DO NOTHING;
        """

        # Insert message
        insert_message_sql = """
        INSERT INTO messages (
            operation_id, session_id, action_id, timestamp, system_prompt, user_prompt, response,
            assistant_message, history_messages, completion_args, error_messages
        ) VALUES (
            %(operation_id)s, %(session_id)s, %(action_id)s, %(timestamp)s, %(system_prompt)s, %(user_prompt)s, %(response)s,
            %(assistant_message)s, %(history_messages)s, %(completion_args)s, %(error_messages)s
        );
        """

        # Insert metrics
        insert_metrics_sql = """
        INSERT INTO metrics (
            operation_id, operation_type, provider, model, success, temperature, max_tokens, input_tokens, output_tokens, total_tokens, cost, latency_ms
        ) VALUES (
            %(operation_id)s, %(operation_type)s, %(provider)s, %(model)s, %(success)s, %(temperature)s, %(max_tokens)s, %(input_tokens)s, %(output_tokens)s,
            %(total_tokens)s, %(cost)s, %(latency_ms)s
        );
        """

        data = record.serialize_model()

        cur = self.db_conn.cursor()
        # Insert session record
        cur.execute(insert_session_sql, {
            'session_id': data.get('session_id'),
            'workspace': data.get('workspace'),
            'agent_id': data.get('agent_id')
        })
        # Insert message record
        cur.execute(insert_message_sql, {
            'operation_id': data.get('operation_id'),
            'session_id': data.get('session_id'),
            'action_id': data.get('action_id'),
            'timestamp': data.get('timestamp'),
            'system_prompt': data.get('system_prompt'),
            'user_prompt': data.get('user_prompt'),
            'response': data.get('response'),
            'assistant_message': data.get('assistant_message'),
            'history_messages': data.get('history_messages'),
            'completion_args': data.get('completion_args'),
            'error_messages': data.get('error_messages')
        })
        # Insert metrics record
        cur.execute(insert_metrics_sql, {
            'operation_id': data.get('operation_id'),
            'operation_type': data.get('operation_type'),
            'provider': data.get('provider'),
            'model': data.get('model'),
            'success': data.get('success'),
            'temperature': data.get('temperature'),
            'max_tokens': data.get('max_tokens'),
            'input_tokens': data.get('input_tokens'),
            'output_tokens': data.get('output_tokens'),
            'total_tokens': data.get('total_tokens'),
            'cost': data.get('cost'),
            'latency_ms': data.get('latency_ms')
        })

        self.db_conn.commit()
        cur.close()
        self._last_inserted_record = data.get('operation_id')

    @classmethod
    def polars_from_pg(cls,
                       agent_id: Optional[str] = None,
                       action_id: Optional[str] = None,
                       session_id: Optional[str] = None,
                       workspace: Optional[str] = None,
                       start_date: Optional[str] = None,  # if you later decide to add a timestamp column
                       end_date: Optional[str] = None) -> "pl.DataFrame":  # noqa: F821
        """
        Query the PostgreSQL database (joining sessions, messages, and metrics)
        and return results as a Polars DataFrame.
        """
        try:
            import polars as pl
            import psycopg2
            import psycopg2.extras
        except ModuleNotFoundError:
            print("pip install aicore[pg,dashboard] for PostgreSQL and Polars integration")
            return None
        
        conn_str = os.environ.get("PG_CONNECTION_STRING")
        if not conn_str:
            print("PostgreSQL connection string not found in environment variables")
            return None

        try:
            conn = psycopg2.connect(conn_str)
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
            return None

        query = """
        SELECT 
            s.session_id, s.workspace, s.agent_id,
            m.action_id, m.operation_id, m.timestamp, m.system_prompt, m.user_prompt, m.response,
            m.assistant_message, m.history_messages, m.completion_args, m.error_messages,
            met.operation_type, met.provider, met.model, met.success, met.temperature, met.max_tokens, met.input_tokens, met.output_tokens, met.total_tokens,
            met.cost, met.latency_ms
        FROM sessions s
        JOIN messages m ON s.session_id = m.session_id
        JOIN metrics met ON m.operation_id = met.operation_id
        WHERE 1=1
        """
        params = {}

        if agent_id:
            query += " AND s.agent_id = %(agent_id)s"
            params['agent_id'] = agent_id

        if action_id:
            query += " AND m.action_id = %(action_id)s"
            params['action_id'] = action_id

        if session_id:
            query += " AND s.session_id = %(session_id)s"
            params['session_id'] = session_id

        if workspace:
            query += " AND s.workspace = %(workspace)s"
            params['workspace'] = workspace

        # Note: If you add a timestamp to messages, you can filter by date here.
        query += " ORDER BY m.operation_id DESC"

        try:
            import polars as pl
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            conn.close()

            if not results:
                return pl.DataFrame()

            records = [dict(row) for row in results]
            return pl.from_dicts(records)
        except Exception as e:
            print(f"Error executing database query: {str(e)}")
            if conn:
                conn.close()
            return None

    @classmethod
    def get_filter_options(cls) -> Dict[str, List[str]]:
        """
        Query the database to get unique filter values.
        For this schema, we provide filters for agent_id, session_id, and workspace.
        """
        try:
            import psycopg2
        except ModuleNotFoundError:
            print("pip install aicore[pg] for PostgreSQL integration")
            return {}

        conn_str = os.environ.get("PG_CONNECTION_STRING")
        if not conn_str:
            print("PostgreSQL connection string not found in environment variables")
            return {}

        try:
            conn = psycopg2.connect(conn_str)
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
            return {}

        filter_fields = {
            'agent_id': 'agent_id',
            'session_id': 'session_id',
            'workspace': 'workspace'
        }

        filter_options = {}
        cur = conn.cursor()
        try:
            for key, field in filter_fields.items():
                query = f"SELECT DISTINCT {field} FROM sessions WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}"
                cur.execute(query)
                results = cur.fetchall()
                filter_options[key] = [row[0] for row in results if row[0]]
        except Exception as e:
            print(f"Error retrieving filter options: {str(e)}")
        finally:
            cur.close()
            conn.close()

        return filter_options

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
            import psycopg2
            import psycopg2.extras
        except ModuleNotFoundError:
            print("pip install aicore[pg] for PostgreSQL integration")
            return {}

        conn_str = os.environ.get("PG_CONNECTION_STRING")
        if not conn_str:
            print("PostgreSQL connection string not found in environment variables")
            return {}

        try:
            conn = psycopg2.connect(conn_str)
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
            return {}

        # Build a query that joins sessions and metrics (via messages)
        where_clause = "WHERE 1=1"
        params = {}

        if agent_id:
            where_clause += " AND s.agent_id = %(agent_id)s"
            params['agent_id'] = agent_id

        if session_id:
            where_clause += " AND s.session_id = %(session_id)s"
            params['session_id'] = session_id

        if workspace:
            where_clause += " AND s.workspace = %(workspace)s"
            params['workspace'] = workspace

        query = f"""
        SELECT 
            COUNT(*) as total_operations,
            AVG(met.latency_ms) as avg_latency_ms,
            SUM(met.input_tokens) as total_input_tokens,
            SUM(met.output_tokens) as total_output_tokens,
            SUM(met.total_tokens) as total_tokens,
            SUM(met.cost) as total_cost
        FROM sessions s
        JOIN messages m ON s.session_id = m.session_id
        JOIN metrics met ON m.operation_id = met.operation_id
        {where_clause}
        """
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(query, params)
            result = dict(cur.fetchone())
            cur.close()
            conn.close()
            return result
        except Exception as e:
            print(f"Error executing metrics query: {str(e)}")
            if conn:
                conn.close()
            return {}


if __name__ == "__main__":
    LlmOperationCollector()
    df = LlmOperationCollector.polars_from_pg()
    print(df.columns)
    print(df)