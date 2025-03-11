
"""
Pytest tests for the PostgreSQL integration in the observability module's LlmOperationCollector.
These tests ensure that if a PG_CONNECTION_STRING is set, the collector attempts to connect to
PostgreSQL, creates the 'observability' table if it does not exist, and inserts records by executing
the proper SQL commands using a mocked database connection.
"""

import os
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import pytest
import psycopg2

from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE
from aicore.observability.collector import LlmOperationCollector, LlmOperationRecord


# --- Helpers for Fake PostgreSQL Connection and Cursor ---

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


# --- Tests for LlmOperationCollector PostgreSQL integration ---

class TestLlmOperationCollector:
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
            def execute(self, query, params):
                executed_queries.append(query)

        class FakeConnForInsert(FakeConn):
            def cursor(self):
                return FakeCursorForInsert(executed_queries)

        monkeypatch.setattr(psycopg2, "connect", lambda conn_str: FakeConnForInsert())

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

        # Patch psycopg2.connect to raise an exception.
        monkeypatch.setattr(psycopg2, "connect", lambda conn_str: (_ for _ in ()).throw(Exception("Connection failed")))
        collector = LlmOperationCollector()
        assert collector.db_conn is None, "Database connection should be None after a connection failure."


# --- Integration tests using temporary file storage for observable data ---

class TestIntegration:
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