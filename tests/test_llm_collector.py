import pytest
import json
import os
from unittest.mock import patch, mock_open
from datetime import datetime
import tempfile
from pathlib import Path

import psycopg2

from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE
# Use the collector module that now also supports PostgreSQL.
from aicore.observability.collector import LlmOperationCollector, LlmOperationRecord

# --- Helpers for Fake PostgreSQL Connection and Cursor (V2) ---

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

class TestLlmOperationCollectorPostgres:
    def test_db_connection_established(self, monkeypatch):
        """
        Test that, when PG_CONNECTION_STRING is set, the collector attempts a PostgreSQL connection.
        """
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        # Patch psycopg2.connect to return a fake connection.
        monkeypatch.setattr(psycopg2, "connect", lambda conn_str: FakeConn())
        collector = LlmOperationCollector()
        assert collector.db_conn is not None, "Expected a valid database connection."
    
    def test_db_table_creation_called(self, monkeypatch):
        """
        Test that the collector executes the SQL to create the 'observability' table if it does not exist.
        """
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        executed_queries = []

        class FakeCursorForTable(FakeCursor):
            pass

        class FakeConnForTable(FakeConn):
            def cursor(self):
                return FakeCursorForTable(executed_queries)

        monkeypatch.setattr(psycopg2, "connect", lambda conn_str: FakeConnForTable())
        _ = LlmOperationCollector()
        query_found = any("CREATE TABLE IF NOT EXISTS observability" in q for q in executed_queries)
        assert query_found, "Table creation SQL was not executed."
    
    def test_record_insertion_executes_sql(self, monkeypatch):
        """
        Test that record insertion calls the SQL INSERT command on the PostgreSQL connection.
        """
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        executed_queries = []
        
        class FakeCursorForInsert(FakeCursor):
            def execute(self, query, params=None):
                executed_queries.append(query)
        
        class FakeConnForInsert(FakeConn):
            def cursor(self):
                return FakeCursorForInsert(executed_queries)
        
        # Create a single connection instance to be reused
        fake_conn = FakeConnForInsert()
        monkeypatch.setattr(psycopg2, "connect", lambda conn_str: fake_conn)
        
        collector = LlmOperationCollector()
        
        # Clear the queries after initialization
        executed_queries.clear()
        
        record = collector.record_completion(
            completion_args={"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
            operation_type="completion",
            provider="openai",
            response="Test response",
            input_tokens=10,
            output_tokens=5,
            latency_ms=150.0
        )
        
        # Print for debugging
        print(f"Executed queries: {executed_queries}")
        
        insertion_queries = [q for q in executed_queries if "INSERT INTO observability" in q]
        assert len(insertion_queries) == 1, "Record insertion SQL was not executed properly."

    def test_no_pg_connection_when_env_missing(self, monkeypatch):
        """
        Test that if the PG_CONNECTION_STRING environment variable is not present,
        no PostgreSQL connection is attempted.
        """
        monkeypatch.delenv("PG_CONNECTION_STRING", raising=False)
        collector = LlmOperationCollector()
        assert collector.db_conn is None, "Database connection should remain None without PG_CONNECTION_STRING."

    def test_connection_failure_handling(self, monkeypatch):
        """
        Test that if psycopg2.connect fails (raises an exception), the collector handles it gracefully.
        """
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        monkeypatch.setattr(psycopg2, "connect", lambda conn_str: (_ for _ in ()).throw(Exception("Connection failed")))
        collector = LlmOperationCollector()
        assert collector.db_conn is None, "Database connection should be None after a connection failure."

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
            
            # Create a collector with a storage path set.
            collector = LlmOperationCollector()
            collector.storage_path = temp_file
            
            # Record a completion.
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
            
            # Verify the file was created and contains the record.
            assert os.path.exists(temp_file), "Storage file was not created."
            
            with open(temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert len(data) >= 1, "Expected at least one record in the storage file."
            record = data[0]
            assert record["provider"] == "openai"
            assert record["model"] == "gpt-4"
            assert record["response"] == "Hi there!"
            assert record["temperature"] == 0.5

class TestLlmOperationCollectorPolarsFromPg:
    """Tests for the polars_from_pg classmethod."""

    def test_polars_from_pg_no_connection_string(self, monkeypatch):
        """Test behavior when no PG_CONNECTION_STRING is available."""
        monkeypatch.delenv("PG_CONNECTION_STRING", raising=False)
        
        # Mock polars import to avoid dependency issues in test environment
        with patch("importlib.import_module") as mock_import:
            mock_import.return_value = None
            result = LlmOperationCollector.polars_from_pg()
            assert result is None

    def test_polars_from_pg_missing_polars(self, monkeypatch):
        """Test behavior when polars module is not available."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        # Simulate ModuleNotFoundError when importing polars
        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = ModuleNotFoundError("No module named 'polars'")
            result = LlmOperationCollector.polars_from_pg()
            assert result is None

    def test_polars_from_pg_connection_error(self, monkeypatch):
        """Test handling of database connection errors."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        # Mock polars module
        mock_polars = pytest.importorskip("polars", reason="Polars is required for this test")
        
        # Mock psycopg2.connect to raise an exception
        with patch("psycopg2.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection error")
            result = LlmOperationCollector.polars_from_pg()
            assert result is None

    # @pytest.mark.parametrize(
    #     "filters,expected_query_parts",
    #     [
    #         (
    #             {"provider": "groq"}, 
    #             ["provider = %(provider)s"]
    #         ),
    #         (
    #             {"model": "deepseek-r1-distill-llama-70b"}, 
    #             ["model = %(model)s"]
    #         ),
    #         (
    #             {"agent_id": "Zé"}, 
    #             ["agent_id = %(agent_id)s"]
    #         ),
    #         (
    #             {"session_id": "01JP14ZPH4VGS3BRVDAR3CKM67"}, 
    #             ["session_id = %(session_id)s"]
    #         ),
    #         (
    #             {"workspace": "workspace1"}, 
    #             ["workspace = %(workspace)s"]
    #         ),
    #         (
    #             {"start_date": "2025-03-01T00:00:00"}, 
    #             ["timestamp >= %(start_date)s"]
    #         ),
    #         (
    #             {"end_date": "2025-03-31T23:59:59"}, 
    #             ["timestamp <= %(end_date)s"]
    #         ),
    #         (
    #             {
    #                 "provider": "groq",
    #                 "model": "deepseek-r1-distill-llama-70b",
    #                 "start_date": "2025-03-01T00:00:00",
    #                 "end_date": "2025-03-31T23:59:59"
    #             }, 
    #             [
    #                 "provider = %(provider)s",
    #                 "model = %(model)s",
    #                 "timestamp >= %(start_date)s",
    #                 "timestamp <= %(end_date)s"
    #             ]
    #         ),
    #     ]
    # )
    # def test_polars_from_pg_filter_application(self, monkeypatch, filters, expected_query_parts):
    #     """Test that filters are correctly applied to the SQL query."""
    #     test_conn_str = "postgresql://user:pass@localhost/test_db"
    #     monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
    #     # Create a test cursor that captures the executed query
    #     executed_queries = []
    #     executed_params = []
        
    #     class TestCursor:
    #         def __init__(self):
    #             pass
                
    #         def execute(self, query, params=None):
    #             executed_queries.append(query)
    #             executed_params.append(params)
                
    #         def fetchall(self):
    #             return []
                
    #         def close(self):
    #             pass
        
    #     class TestConnection:
    #         def __init__(self):
    #             pass
                
    #         def cursor(self, cursor_factory=None):
    #             return TestCursor()
                
    #         def close(self):
    #             pass
        
    #     # Mock necessary imports and functions
    #     with patch("psycopg2.connect", return_value=TestConnection()):
    #         with patch("polars.from_dicts") as mock_from_dicts:
    #             mock_from_dicts.return_value = "polars_dataframe"
                
    #             # Call the method with the test filters
    #             LlmOperationCollector.polars_from_pg(**filters)
                
    #             # Check that the query was executed with the correct parameters
    #             assert len(executed_queries) == 1
    #             query = executed_queries[0]
                
    #             # Check that all expected parts are in the query
    #             for part in expected_query_parts:
    #                 assert part in query
                    
    #             # Check that parameters were passed correctly
    #             assert len(executed_params) == 1
    #             params = executed_params[0]
                
    #             for key, value in filters.items():
    #                 assert key in params
    #                 assert params[key] == value
    
    def test_polars_from_pg_successful_query(self, monkeypatch):
        """Test successful query execution and DataFrame creation."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        # Mock data to return from the database
        mock_data = [
            {"operation_id": "op1", "provider": "groq", "model": "model1", "timestamp": "2025-03-10T12:00:00"},
            {"operation_id": "op2", "provider": "gemini", "model": "model2", "timestamp": "2025-03-11T12:00:00"}
        ]
        
        class TestDictCursor:
            def __init__(self):
                self.mock_data = mock_data
            
            def execute(self, query, params=None):
                pass
                
            def fetchall(self):
                return self.mock_data
                
            def close(self):
                pass
        
        class TestConnection:
            def __init__(self):
                pass
                
            def cursor(self, cursor_factory=None):
                return TestDictCursor()
                
            def close(self):
                pass
        
        # Mock necessary imports and functions
        with patch("psycopg2.connect", return_value=TestConnection()):
            with patch("psycopg2.extras.DictCursor"):
                with patch("polars.from_dicts") as mock_from_dicts:
                    mock_from_dicts.return_value = "polars_dataframe"
                    
                    # Call the method
                    result = LlmOperationCollector.polars_from_pg(provider="groq")
                    
                    # Check the result
                    assert result == "polars_dataframe"
                    
                    # Verify that from_dicts was called with the mock data
                    mock_from_dicts.assert_called_once()
                    args, _ = mock_from_dicts.call_args
                    assert args[0] == mock_data


class TestLlmOperationCollectorGetFilterOptions:
    """Tests for the get_filter_options method."""
    
    def test_get_filter_options_no_connection_string(self, monkeypatch):
        """Test behavior when no PG_CONNECTION_STRING is available."""
        monkeypatch.delenv("PG_CONNECTION_STRING", raising=False)
        result = LlmOperationCollector.get_filter_options()
        assert result == {}
    
    def test_get_filter_options_connection_error(self, monkeypatch):
        """Test handling of database connection errors."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        # Mock psycopg2.connect to raise an exception
        with patch("psycopg2.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection error")
            result = LlmOperationCollector.get_filter_options()
            assert result == {}
    
    def test_get_filter_options_successful_query(self, monkeypatch):
        """Test successful retrieval of filter options."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        # Define mock data for each filter query
        query_results = {
            "SELECT DISTINCT provider FROM observability WHERE provider IS NOT NULL AND provider != '' ORDER BY provider": 
                [("groq",), ("gemini",)],
            "SELECT DISTINCT model FROM observability WHERE model IS NOT NULL AND model != '' ORDER BY model": 
                [("deepseek-r1-distill-llama-70b",), ("gemini-2.0-flash-exp",)],
            "SELECT DISTINCT agent_id FROM observability WHERE agent_id IS NOT NULL AND agent_id != '' ORDER BY agent_id": 
                [("Zé",), ("")],
            "SELECT DISTINCT session_id FROM observability WHERE session_id IS NOT NULL AND session_id != '' ORDER BY session_id": 
                [("01JP14ZPH4VGS3BRVDAR3CKM67",)],
            "SELECT DISTINCT workspace FROM observability WHERE workspace IS NOT NULL AND workspace != '' ORDER BY workspace": 
                [("",)],
            "SELECT MIN(timestamp), MAX(timestamp) FROM observability": 
                [("2025-03-10T23:07:10.447968", "2025-03-10T23:07:12.761532")]
        }
        
        class TestCursor:
            def __init__(self):
                self.current_query = None
                
            def execute(self, query, params=None):
                self.current_query = query
                
            def fetchall(self):
                if self.current_query in query_results:
                    return query_results[self.current_query]
                return []
                
            def fetchone(self):
                if self.current_query in query_results:
                    return query_results[self.current_query][0]
                return None
                
            def close(self):
                pass
        
        class TestConnection:
            def __init__(self):
                pass
                
            def cursor(self):
                return TestCursor()
                
            def close(self):
                pass
        
        # Mock psycopg2.connect
        with patch("psycopg2.connect", return_value=TestConnection()):
            result = LlmOperationCollector.get_filter_options()
            
            # Check that the result contains all expected filters
            assert "provider" in result
            assert "model" in result
            assert "agent_id" in result
            assert "session_id" in result
            assert "workspace" in result
            assert "date_range" in result
            
            # Check specific values
            assert result["provider"] == ["groq", "gemini"]
            assert result["model"] == ["deepseek-r1-distill-llama-70b", "gemini-2.0-flash-exp"]
            assert result["agent_id"] == ["Zé"]  # Empty string should be filtered out
            assert result["session_id"] == ["01JP14ZPH4VGS3BRVDAR3CKM67"]
            assert result["workspace"] == []  # Empty string should be filtered out
            assert result["date_range"] == ["2025-03-10T23:07:10.447968", "2025-03-10T23:07:12.761532"]
    
    def test_get_filter_options_query_error(self, monkeypatch):
        """Test handling of query execution errors."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        class TestCursor:
            def __init__(self):
                pass
                
            def execute(self, query, params=None):
                raise Exception("Query execution error")
                
            def close(self):
                pass
        
        class TestConnection:
            def __init__(self):
                pass
                
            def cursor(self):
                return TestCursor()
                
            def close(self):
                pass
        
        # Mock psycopg2.connect
        with patch("psycopg2.connect", return_value=TestConnection()):
            result = LlmOperationCollector.get_filter_options()
            
            # Should return empty dict on error
            assert result == {}


class TestLlmOperationCollectorGetMetricsSummary:
    """Tests for the get_metrics_summary method."""
    
    def test_get_metrics_summary_no_connection_string(self, monkeypatch):
        """Test behavior when no PG_CONNECTION_STRING is available."""
        monkeypatch.delenv("PG_CONNECTION_STRING", raising=False)
        result = LlmOperationCollector.get_metrics_summary()
        assert result == {}
    
    def test_get_metrics_summary_connection_error(self, monkeypatch):
        """Test handling of database connection errors."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        # Mock psycopg2.connect to raise an exception
        with patch("psycopg2.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection error")
            result = LlmOperationCollector.get_metrics_summary()
            assert result == {}
    
    @pytest.mark.parametrize(
        "filters,expected_where_parts",
        [
            (
                {"provider": "groq"}, 
                ["provider = %(provider)s"]
            ),
            (
                {"model": "deepseek-r1-distill-llama-70b"}, 
                ["model = %(model)s"]
            ),
            (
                {
                    "provider": "groq",
                    "model": "deepseek-r1-distill-llama-70b",
                    "start_date": "2025-03-01T00:00:00",
                    "end_date": "2025-03-31T23:59:59"
                }, 
                [
                    "provider = %(provider)s",
                    "model = %(model)s",
                    "timestamp >= %(start_date)s",
                    "timestamp <= %(end_date)s"
                ]
            ),
        ]
    )
    def test_get_metrics_summary_filter_application(self, monkeypatch, filters, expected_where_parts):
        """Test that filters are correctly applied to the metrics query."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        # Track executed queries and parameters
        executed_queries = []
        executed_params = []
        
        class TestDictCursor:
            def __init__(self):
                pass
                
            def execute(self, query, params=None):
                executed_queries.append(query)
                executed_params.append(params)
                
            def fetchone(self):
                return {
                    "total_operations": 100,
                    "successful_operations": 95,
                    "failed_operations": 5,
                    "avg_latency_ms": 150.5,
                    "total_input_tokens": 5000,
                    "total_output_tokens": 3000,
                    "total_tokens": 8000,
                    "total_cost": 0.25,
                    "provider_count": 2,
                    "model_count": 3,
                    "session_count": 10
                }
                
            def fetchall(self):
                query = executed_queries[-1] if executed_queries else ""
                if "provider" in query and "GROUP BY provider" in query:
                    return [
                        {"provider": "groq", "count": 60},
                        {"provider": "gemini", "count": 40}
                    ]
                elif "model" in query and "GROUP BY model" in query:
                    return [
                        {"model": "deepseek-r1-distill-llama-70b", "count": 50},
                        {"model": "gemini-2.0-flash-exp", "count": 50}
                    ]
                return []
                
            def close(self):
                pass
        
        class TestConnection:
            def __init__(self):
                pass
                
            def cursor(self, cursor_factory=None):
                return TestDictCursor()
                
            def close(self):
                pass
        
        # Mock psycopg2.connect
        with patch("psycopg2.connect", return_value=TestConnection()):
            with patch("psycopg2.extras.DictCursor"):
                result = LlmOperationCollector.get_metrics_summary(**filters)
                
                # Check that at least 3 queries were executed (main metrics, provider distribution, model distribution)
                assert len(executed_queries) >= 3
                
                # Check filter application in WHERE clauses
                main_query = executed_queries[0]
                for part in expected_where_parts:
                    assert part in main_query
                
                # Check that the result contains expected fields
                assert "total_operations" in result
                assert "successful_operations" in result
                assert "failed_operations" in result
                assert "avg_latency_ms" in result
                assert "total_input_tokens" in result
                assert "total_output_tokens" in result
                assert "total_tokens" in result
                assert "total_cost" in result
                assert "provider_distribution" in result
                assert "model_distribution" in result
                
                # Check specific values
                assert result["total_operations"] == 100
                assert result["successful_operations"] == 95
                assert result["failed_operations"] == 5
                assert result["provider_distribution"] == {"groq": 60, "gemini": 40}
                assert result["model_distribution"] == {"deepseek-r1-distill-llama-70b": 50, "gemini-2.0-flash-exp": 50}
    
    def test_get_metrics_summary_query_error(self, monkeypatch):
        """Test handling of query execution errors."""
        test_conn_str = "postgresql://user:pass@localhost/test_db"
        monkeypatch.setenv("PG_CONNECTION_STRING", test_conn_str)
        
        class TestDictCursor:
            def __init__(self):
                pass
                
            def execute(self, query, params=None):
                raise Exception("Query execution error")
                
            def close(self):
                pass
        
        class TestConnection:
            def __init__(self):
                pass
                
            def cursor(self, cursor_factory=None):
                return TestDictCursor()
                
            def close(self):
                pass
        
        # Mock psycopg2.connect
        with patch("psycopg2.connect", return_value=TestConnection()):
            with patch("psycopg2.extras.DictCursor"):
                result = LlmOperationCollector.get_metrics_summary()
                
                # Should return empty dict on error
                assert result == {}
