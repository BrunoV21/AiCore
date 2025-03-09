import pytest
import json
import os
from unittest.mock import patch, mock_open
from datetime import datetime
import tempfile
from pathlib import Path

from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE
from aicore.observability import LlmOperationCollector, LlmOperationRecord

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
        assert record.success == False  # Since response is None
        
        # Test with response
        record.response = "Test response"
        assert record.success is True


class TestLlmOperationCollector:
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
            assert collector.storage_path == Path(DEFAULT_OBSERVABILITY_DIR) / DEFAULT_OBSERVABILITY_FILE


class TestIntegration:
    """Integration tests for the collector and record classes."""
    
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