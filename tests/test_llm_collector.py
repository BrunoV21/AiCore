import os
import ulid
import json
import pytest
import tempfile
from unittest.mock import patch, MagicMock, mock_open
import polars as pl
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE, DEFAULT_ENCODING
# Use the collector module that now also supports PostgreSQL.
from aicore.observability.collector import LlmOperationCollector, LlmOperationRecord
from aicore.observability.models import Session, Message, Metric

class FakeCursor:
    """A fake database cursor that tracks executed SQL commands."""
    def __init__(self, executed_queries: list):
        self.executed_queries = executed_queries

    def execute(self, query, params=None):
        self.executed_queries.append(query)

    def close(self):
        pass

class FakeConn:
    """A fake PostgreSQL connection that provides a fake cursor and commit behaviour."""
    def __init__(self, executed_queries: list = None):
        if executed_queries is None:
            executed_queries = []
        self.executed_queries = executed_queries

    def cursor(self):
        return FakeCursor(self.executed_queries)

    def commit(self):
        pass

class TestLlmOperationRecord:
    def test_init_with_minimal_args(self):
        """Test initializing with only required fields."""
        record = LlmOperationRecord(
            operation_type="completion",
            provider="openai",
            completion_args={"model": "gpt-4"},
            latency_ms=100.0
        )
        assert record.operation_type == "completion"
        assert record.provider == "openai"
        assert record.latency_ms == 100.0
        assert record.completion_args == {"model": "gpt-4"}
        assert record.timestamp is not None
        assert record.operation_id is not None

    def test_field_validators(self):
        """Test field validators work correctly."""
        # Test timestamp validator
        record = LlmOperationRecord(
            operation_type="completion",
            provider="openai",
            completion_args={"model": "gpt-4"},
            latency_ms=100.0
        )
        assert isinstance(record.timestamp, str)

        # Test completion_args validator with string
        json_args = json.dumps({"model": "gpt-4", "temperature": 0.7})
        record = LlmOperationRecord(
            operation_type="completion",
            provider="openai",
            completion_args=json_args,
            latency_ms=100.0
        )
        assert isinstance(record.completion_args, dict)
        assert record.completion_args["model"] == "gpt-4"

        # Test response validator with dict
        response_dict = {"choices": [{"message": {"content": "Hello"}}]}
        record = LlmOperationRecord(
            operation_type="completion",
            provider="openai",
            completion_args={"model": "gpt-4"},
            latency_ms=100.0,
            response=response_dict
        )
        assert isinstance(record.response, str)
        assert "Hello" in record.response

    def test_computed_fields(self):
        """Test computed fields return correct values."""
        record = LlmOperationRecord(
            operation_type="completion",
            provider="openai",
            completion_args={
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 1000,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"}
                ]
            },
            input_tokens=10,
            output_tokens=5,
            latency_ms=100.0
        )
        assert record.model == "gpt-4"
        assert record.temperature == 0.7
        assert record.max_tokens == 1000
        assert record.system_prompt == "You are a helpful assistant"
        assert record.user_prompt == "Hello"
        assert record.assistant_message == "Hi there"
        assert record.total_tokens == 15
        assert record.success is False  # Since response is None

        # Test with response
        record.response = "Test response"
        assert record.success is True

class TestLlmOperationCollectorFileStorage:
    def test_init(self):
        """Test initialization of the collector."""
        collector = LlmOperationCollector()
        assert collector.root == []
        assert collector.storage_path is None

    def test_storage_path_setter(self):
        """Test setting storage path."""
        collector = LlmOperationCollector()
        collector.storage_path = "test/path.json"
        assert collector.storage_path == "test/path.json"
        
        # Test with Path object
        path_obj = Path("/tmp/test.json")
        collector.storage_path = path_obj
        assert collector.storage_path == path_obj

    def test_record_completion(self):
        """Test recording a completion operation."""
        collector = LlmOperationCollector()
        record = collector.record_completion(
            completion_args={"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
            operation_type="completion",
            provider="openai",
            response="Test response",
            input_tokens=10,
            output_tokens=5,
            latency_ms=150.0
        )
        assert len(collector.root) == 1
        assert collector.root[0] == record
        assert record.provider == "openai"
        assert record.operation_type == "completion"
        assert record.response == "Test response"
        assert record.input_tokens == 10
        assert record.output_tokens == 5
        assert record.latency_ms == 150.0

    def test_clean_completion_args(self):
        """Test cleaning of sensitive information from completion arguments."""
        collector = LlmOperationCollector()
        args = {
            "model": "gpt-4",
            "api_key": "sk-sensitive-key-12345",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        cleaned = collector._clean_completion_args(args)
        assert "api_key" not in cleaned
        assert cleaned["model"] == "gpt-4"
        assert cleaned["messages"] == [{"role": "user", "content": "Hello"}]

    @patch.dict('os.environ', {"OBSERVABILITY_DATA_DEFAULT_FILE": "/env/path.json"})
    def test_from_observable_storage_path_with_env(self):
        """Test creating collector with environment variable path."""
        collector = LlmOperationCollector.fom_observable_storage_path()
        assert collector.storage_path == "/env/path.json"

    def test_from_observable_storage_path_with_param(self):
        """Test creating collector with provided path."""
        collector = LlmOperationCollector.fom_observable_storage_path("/custom/path.json")
        assert collector.storage_path == "/custom/path.json"

    @patch('pathlib.Path.__truediv__', return_value=Path("/default/path/llm_operations.json"))
    def test_from_observable_storage_path_default(self, mock_truediv):
        """Test creating collector with default path."""
        with patch.dict('os.environ', {}, clear=True):
            collector = LlmOperationCollector.fom_observable_storage_path()
            expected_path = Path(DEFAULT_OBSERVABILITY_DIR) / DEFAULT_OBSERVABILITY_FILE
            assert collector.storage_path == expected_path


class TestIntegrationFileStorage:
    """Integration tests for the collector and record classes (file storage)."""
    
    def test_end_to_end(self):
        """Test an end-to-end flow with a temporary file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, "test_records.json")
            
            # Create collector with storage path
            collector = LlmOperationCollector()
            collector.storage_path = temp_file
            
            # Record a completion
            collector.record_completion(
                completion_args={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "temperature": 0.5
                },
                operation_type="completion",
                provider="openai",
                response="Hi there!",
                input_tokens=5,
                output_tokens=3,
                latency_ms=120.0
            )
            
            # Verify the file was created and contains the record
            assert os.path.exists(temp_file)
            
            with open(temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Expect a list of serialized records (the structure remains as before)
            assert len(data) == 1
            record = data[0]
            assert record["provider"] == "openai"
            assert record["model"] == "gpt-4"
            assert record["response"] == "Hi there!"
            assert record["temperature"] == 0.5
            
            # Add another record
            collector.record_completion(
                completion_args={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "How are you?"}]
                },
                operation_type="completion",
                provider="openai",
                response="I'm fine, thank you!",
                input_tokens=4,
                output_tokens=5,
                latency_ms=80.0
            )
            
            # Verify both records are in the file
            with open(temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            assert len(data) == 2
            assert data[1]["model"] == "gpt-3.5-turbo"
            assert data[1]["response"] == "I'm fine, thank you!"


# --- Integration Storage Tests (File) ---
class TestIntegrationStorage:
    """
    Integration tests for LlmOperationCollector and LlmOperationRecord, including file storage.
    """
    def test_end_to_end_storage(self):
        """
        Test an end-to-end flow where a record is stored in a temporary file.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, "test_records.json")
            
            collector = LlmOperationCollector()
            collector.storage_path = temp_file
            
            collector.record_completion(
                completion_args={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "temperature": 0.5
                },
                operation_type="completion",
                provider="openai",
                response="Hi there!",
                input_tokens=5,
                output_tokens=3,
                latency_ms=120.0
            )
            
            assert os.path.exists(temp_file), "Storage file was not created."
            
            with open(temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert len(data) >= 1, "Expected at least one record in the storage file."
            record = data[0]
            assert record["provider"] == "openai"
            assert record["model"] == "gpt-4"
            assert record["response"] == "Hi there!"
            assert record["temperature"] == 0.5


@pytest.fixture
def in_memory_collector(monkeypatch, tmp_path):
    """
    Create a collector with an in-memory SQLite DB and temporary file storage.
    """
    # Use in-memory SQLite for testing DB operations that occur within the same collector instance.
    monkeypatch.setenv("CONNECTION_STRING", "sqlite:///:memory:")
    collector = LlmOperationCollector().init_dbsession()
    storage_file = tmp_path / "observability.json"
    collector.storage_path = str(storage_file)
    return collector


@pytest.fixture
def file_based_db_collector(monkeypatch, tmp_path):
    """
    Create a collector using a file-based SQLite database. This is necessary for tests that use
    class methods (e.g. polars_from_db, get_filter_options, get_metrics_summary) since these methods
    create a new instance. Using a file-based DB ensures state is shared.
    """
    db_file = tmp_path / "test.db"
    db_url = "sqlite:///" + str(db_file)
    monkeypatch.setenv("CONNECTION_STRING", db_url)
    collector = LlmOperationCollector().init_dbsession()
    # Use a temporary file for file-storage even if not needed by DB methods.
    storage_file = tmp_path / "observability.json"
    collector.storage_path = str(storage_file)
    return collector


# For tests that call class methods (which create a new instance) we patch __init__
# so that the new instance is set up with the same engine/DBSession.
def patch_init_with_db(monkeypatch, db_url: str):
    engine = create_engine(db_url)
    SessionMaker = sessionmaker(bind=engine)
    monkeypatch.setattr(
        LlmOperationCollector,
        "init_dbsession",
        lambda self: (setattr(self, "_dbsession", SessionMaker), setattr(self, "engine", engine))
    )


# === Tests =========================================================

def test_init_dbsession(monkeypatch):
    """Test that init_dbsession properly sets up the DB connection and engine."""
    monkeypatch.setenv("CONNECTION_STRING", "sqlite:///:memory:")
    collector = LlmOperationCollector().init_dbsession()
    assert collector._table_initialized is True
    assert collector._engine is not None
    assert collector._session_factory is not None


def test_clean_completion_args():
    """Test that _clean_completion_args removes the 'api_key' key."""
    args = {"param": "value", "api_key": "secret123"}
    cleaned = LlmOperationCollector._clean_completion_args(args)
    assert "api_key" not in cleaned
    assert cleaned.get("param") == "value"


def test_record_completion_file_storage(in_memory_collector):
    """
    Test that record_completion:
      - Cleans the arguments,
      - Appends the new record to the root,
      - Writes the record to the file (using JSON format).
    """
    args = {"param": "value", "api_key": "should_be_removed"}
    record = in_memory_collector.record_completion(
        completion_args=args,
        operation_type="completion",
        provider="test_provider",
        response="test response",
        session_id="session1",
        workspace="workspace1",
        agent_id="agent1",
        action_id="action1",
        input_tokens=10,
        output_tokens=5,
        cost=0.05,
        latency_ms=100,
        error_message=""
    )
    # Verify the record was appended in memory.
    assert record in in_memory_collector.root

    # Verify the file storage. (The _store_to_file method writes a JSON array.)
    with open(in_memory_collector.storage_path, "r", encoding=DEFAULT_ENCODING) as f:
        data = json.loads(f.read())
    # Look for our record by its operation_id.
    found = any(item.get("operation_id") == record.operation_id for item in data)
    assert found

    # Also ensure the sensitive key was removed in the stored JSON.
    for item in data:
        if item.get("operation_id") == record.operation_id:
            # completion_args was JSON-dumped, so load it back to check.
            completion_args = json.loads(item["completion_args"])
            assert "api_key" not in completion_args


def test_record_completion_db(monkeypatch, tmp_path):
    """
    Test that record_completion inserts records into the database.
    (Here we use an in-memory DB so that the same collector instance is used.)
    """
    monkeypatch.setenv("CONNECTION_STRING", "sqlite:///:memory:")
    collector = LlmOperationCollector().init_dbsession()
    storage_file = tmp_path / "observability.json"
    collector.storage_path = str(storage_file)

    args = {"param": "value", "api_key": "secret123"}
    record = collector.record_completion(
        completion_args=args,
        operation_type="completion",
        provider="test_provider",
        response="test response db",
        session_id="session_db",
        workspace="workspace_db",
        agent_id="agent_db",
        action_id="action_db",
        input_tokens=15,
        output_tokens=7,
        cost=0.10,
        latency_ms=150,
        error_message=""
    )
    # _last_inserted_record should match.
    assert collector._last_inserted_record == record.operation_id

    # Use the collector’s DBSession to query the inserted records.
    session_local = collector._session_factory()
    db_sess = session_local.query(Session).filter_by(session_id=record.session_id).first()
    assert db_sess is not None

    db_message = session_local.query(Message).filter_by(operation_id=record.operation_id).first()
    assert db_message is not None

    db_metric = session_local.query(Metric).filter_by(operation_id=record.operation_id).first()
    assert db_metric is not None

    session_local.close()


def test_polars_from_file(file_based_db_collector, tmp_path):
    """
    Test that polars_from_file returns a non-empty DataFrame when the file contains valid records.
    We simulate file storage by writing a JSON list of a dummy record.
    """
    # Create a dummy record dictionary (mimicking a serialized LlmOperationRecord)
    dummy_record = {
        "session_id": "sess1",
        "workspace": "ws1",
        "agent_id": "agent1",
        "action_id": "act1",
        "timestamp": "2025-03-18T00:00:00Z",
        "operation_id": str(ulid.ulid()),
        "operation_type": "completion",
        "provider": "test",
        "model": "dummy",
        "system_prompt": "",
        "user_prompt": "",
        "response": "ok",
        "success": True,
        "assistant_message": "",
        "history_messages": "",
        "temperature": "",
        "max_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
        "latency_ms": 100.0,
        "error_message": "",
        "completion_args": json.dumps({"param": "value"}, indent=4)
    }
    # Write the dummy record as a JSON list to the storage file.
    with open(file_based_db_collector.storage_path, "w", encoding=DEFAULT_ENCODING) as f:
        f.write(json.dumps([dummy_record]))
    
    df = LlmOperationCollector.polars_from_file(file_based_db_collector.storage_path)
    assert isinstance(df, pl.DataFrame)
    assert not df.is_empty()
    assert "session_id" in df.columns


def test_polars_from_db(monkeypatch, tmp_path):
    """
    Test that polars_from_db returns a DataFrame that includes the inserted record.
    Here we use a file-based SQLite DB so that a new instance (created by the class method)
    sees the inserted record.
    """
    db_file = tmp_path / "test.db"
    db_url = "sqlite:///" + str(db_file)
    monkeypatch.setenv("CONNECTION_STRING", db_url)
    
    # Use file-based DB collector to insert a record.
    collector = LlmOperationCollector().init_dbsession()
    storage_file = tmp_path / "observability.json"
    collector.storage_path = str(storage_file)
    
    args = {"param": "value", "api_key": "secret123"}
    collector.record_completion(
        completion_args=args,
        operation_type="completion",
        provider="db_provider",
        response="db response",
        session_id="sess_db",
        workspace="ws_db",
        agent_id="agent_db",
        action_id="action_db",
        input_tokens=20,
        output_tokens=10,
        cost=0.20,
        latency_ms=200,
        error_message=""
    )
    # Patch __init__ so that new instances used in the class method have a valid DBSession.
    patch_init_with_db(monkeypatch, db_url)
    
    df = LlmOperationCollector.polars_from_db()
    assert isinstance(df, pl.DataFrame)
    assert not df.is_empty()
    expected_cols = ["session_id", "workspace", "agent_id", "action_id", "operation_id"]
    for col in expected_cols:
        assert col in df.columns