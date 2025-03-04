
import pytest
import json
import os
import time
from unittest.mock import MagicMock, patch
from pathlib import Path
import polars as pl
import asyncio

from aicore.observability.collector import LlmOperationCollector, LlmOperationRecord
from aicore.observability.storage import OperationStorage
from aicore.observability.dashboard import ObservabilityDashboard
from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.llm.config import LlmConfig
from aicore.config import ObservabilityConfig, Config


# --- LlmOperationCollector Tests ---

@pytest.fixture
def mock_storage_callback():
    return MagicMock()

@pytest.fixture
def collector(mock_storage_callback):
    return LlmOperationCollector(storage_callback=mock_storage_callback)

def test_collector_initialization(collector, mock_storage_callback):
    """Test that collector initializes correctly with storage callback."""
    assert collector.storage_callback == mock_storage_callback
    assert collector.is_enabled is True

def test_collector_disable(collector):
    """Test that collector can be disabled."""
    collector.is_enabled = False
    assert collector.is_enabled is False

def test_record_operation(collector, mock_storage_callback):
    """Test recording an operation."""
    record = collector.record_operation(
        provider="openai", 
        model="gpt-4",
        operation_type="completion",
        request_args={"prompt": "test prompt", "temperature": 0.7},
        response="test response",
        input_tokens=10,
        output_tokens=20,
        latency_ms=150.5,
        success=True
    )
    
    assert isinstance(record, LlmOperationRecord)
    assert record.provider == "openai"
    assert record.model == "gpt-4"
    assert record.operation_type == "completion"
    assert record.input_tokens == 10
    assert record.output_tokens == 20
    assert record.latency_ms == 150.5
    assert record.success is True
    assert record.request_args["prompt"] == "test prompt"
    assert record.response == "test response"
    
    mock_storage_callback.assert_called_once()
    assert mock_storage_callback.call_args[0][0] == record

def test_record_operation_when_disabled(collector, mock_storage_callback):
    """Test that no recording happens when collector is disabled."""
    collector.is_enabled = False
    record = collector.record_operation(
        provider="openai", 
        model="gpt-4",
        operation_type="completion",
        request_args={"prompt": "test prompt"},
        response="test response",
        latency_ms=150.5
    )
    
    assert record is None
    mock_storage_callback.assert_not_called()

def test_clean_request_args(collector):
    """Test cleaning of sensitive information from request args."""
    args = {
        "prompt": "test prompt",
        "api_key": "sk-sensitive-key",
        "temperature": 0.7
    }
    
    cleaned = collector._clean_request_args(args)
    assert "prompt" in cleaned
    assert "temperature" in cleaned
    assert "api_key" not in cleaned


# --- OperationStorage Tests ---

@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create a temporary directory for storage tests."""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir()
    return storage_dir

@pytest.fixture
def storage(temp_storage_dir):
    return OperationStorage(storage_dir=str(temp_storage_dir), storage_file="test_operations.json")

def test_storage_initialization(storage, temp_storage_dir):
    """Test storage initialization."""
    assert storage.storage_dir == temp_storage_dir
    assert storage.storage_file == temp_storage_dir / "test_operations.json"
    assert temp_storage_dir.exists()

def test_store_record(storage):
    """Test storing a record."""
    record = LlmOperationRecord(
        provider="openai",
        model="gpt-4",
        operation_type="completion",
        input_tokens=10,
        output_tokens=20,
        latency_ms=150.5,
        request_args={"prompt": "test prompt"},
        response="test response"
    )
    
    storage.store_record(record)
    
    # Verify file was created
    assert storage.storage_file.exists()
    
    # Verify data was stored correctly
    df = storage.get_all_records()
    assert not df.is_empty()
    assert df.shape[0] == 1
    assert df.filter(pl.col("provider") == "openai").shape[0] == 1
    assert df.filter(pl.col("model") == "gpt-4").shape[0] == 1

def test_query_records(storage):
    """Test querying records with filters."""
    # Store multiple records
    for i in range(3):
        record = LlmOperationRecord(
            provider="openai" if i < 2 else "mistral",
            model=f"model-{i}",
            operation_type="completion",
            latency_ms=100 + i * 50,
            request_args={"prompt": f"test prompt {i}"},
            response=f"test response {i}"
        )
        storage.store_record(record)
    
    # Query by provider
    openai_records = storage.query_records(filters={"provider": "openai"})
    assert openai_records.shape[0] == 2
    
    # Query by model
    model0_records = storage.query_records(filters={"model": "model-0"})
    assert model0_records.shape[0] == 1
    
    # Test with limit
    limited_records = storage.query_records(limit=2)
    assert limited_records.shape[0] == 2

def test_get_summary_metrics(storage):
    """Test calculating summary metrics."""
    # Store some records with different characteristics
    records = [
        LlmOperationRecord(
            provider="openai",
            model="gpt-4",
            operation_type="completion",
            input_tokens=10,
            output_tokens=20,
            latency_ms=100.0,
            request_args={"prompt": "test prompt 1"},
            success=True
        ),
        LlmOperationRecord(
            provider="mistral",
            model="mistral-medium",
            operation_type="completion",
            input_tokens=15,
            output_tokens=25,
            latency_ms=150.0,
            request_args={"prompt": "test prompt 2"},
            success=False
        )
    ]
    
    for record in records:
        storage.store_record(record)
    
    metrics = storage.get_summary_metrics()
    
    # Check metrics
    assert metrics["total_operations"] == 2
    assert metrics["avg_latency_ms"] == 125.0  # (100 + 150) / 2
    assert metrics["success_rate"] == 50.0  # 1/2 * 100
    assert metrics["total_input_tokens"] == 25  # 10 + 15
    assert metrics["total_output_tokens"] == 45  # 20 + 25
    assert set(metrics["providers"]) == {"openai", "mistral"}
    assert set(metrics["models"]) == {"gpt-4", "mistral-medium"}

def test_clear_older_than(storage):
    """Test removing records older than a specified date."""
    # Create records with different timestamps
    old_record = LlmOperationRecord(
        provider="openai",
        model="gpt-4",
        operation_type="completion",
        timestamp="2022-01-01T00:00:00",
        latency_ms=100.0,
        request_args={"prompt": "old prompt"}
    )
    
    new_record = LlmOperationRecord(
        provider="openai",
        model="gpt-4",
        operation_type="completion",
        timestamp="2023-01-01T00:00:00",
        latency_ms=100.0,
        request_args={"prompt": "new prompt"}
    )
    
    storage.store_record(old_record)
    storage.store_record(new_record)
    
    # Check initial count
    assert storage.get_all_records().shape[0] == 2
    
    # Clear records older than 2022-06-01
    removed = storage.clear_older_than("2022-06-01")
    
    # Verify one record was removed
    assert removed == 1
    assert storage.get_all_records().shape[0] == 1
    
    # Check that only the new record remains
    remaining = storage.get_all_records().to_dicts()[0]
    assert remaining["timestamp"] == "2023-01-01T00:00:00"

def test_export_to_csv(storage, temp_storage_dir):
    """Test exporting records to CSV."""
    # Store a record
    record = LlmOperationRecord(
        provider="openai",
        model="gpt-4",
        operation_type="completion",
        latency_ms=100.0,
        request_args={"prompt": "test prompt"},
        response="test response"
    )
    
    storage.store_record(record)
    
    # Export to CSV
    csv_path = str(temp_storage_dir / "export.csv")
    result = storage.export_to_csv(csv_path)
    
    # Verify export succeeded
    assert result is True
    assert os.path.exists(csv_path)
    
    # Verify CSV content (basic check)
    with open(csv_path, 'r') as f:
        content = f.read()
        assert "openai" in content
        assert "gpt-4" in content
        assert "completion" in content

def test_response_truncation(storage):
    """Test that long responses are truncated when stored."""
    # Create a record with a very long response
    long_response = "x" * 2000  # Much longer than MAX_STORED_RESPONSE_LENGTH
    
    record = LlmOperationRecord(
        provider="openai",
        model="gpt-4",
        operation_type="completion",
        latency_ms=100.0,
        request_args={"prompt": "test prompt"},
        response=long_response
    )
    
    storage.store_record(record)
    
    # Retrieve the stored record
    stored_record = storage.get_all_records().to_dicts()[0]
    
    # Verify response was truncated
    assert len(stored_record["response"]) < len(long_response)
    assert "... [truncated]" in stored_record["response"]

# --- Integration with LLM Provider Tests ---

def test_llm_provider_integration():
    """Test integration with LLM BaseProvider."""
    config = LlmConfig(provider="openai", api_key="test_key", model="gpt-4", temperature=0.7)
    provider = LlmBaseProvider(config=config)
    
    # Verify collector is created
    assert provider.collector is not None
    assert isinstance(provider.collector, LlmOperationCollector)
    
    # Test disabling collection
    provider.disable_collection()
    assert provider.collector.is_enabled is False

@patch('aicore.llm.providers.base_provider.LlmBaseProvider.completion_fn')
def test_operation_tracking_during_completion(mock_completion, tmp_path):
    """Test that operations are properly tracked during completion calls."""
    # Setup
    mock_completion.return_value = MagicMock(
        usage=MagicMock(prompt_tokens=5, completion_tokens=10),
        choices=[MagicMock(message=MagicMock(content="Test response"))]
    )
    
    storage_dir = str(tmp_path / "observability_test")
    storage = OperationStorage(storage_dir=storage_dir)
    
    config = LlmConfig(provider="openai", api_key="test_key", model="gpt-4")
    provider = LlmBaseProvider(config=config)
    provider.collector = LlmOperationCollector(storage_callback=storage.store_record)
    
    # Mock the normalize_fn to handle our mock response
    provider.normalize_fn = lambda x: x.choices
    
    # Execute
    provider.complete("Test prompt", stream=False)
    
    # Verify
    records = storage.get_all_records()
    assert not records.is_empty()
    record = records.to_dicts()[0]
    
    assert record["provider"] == "openai"
    assert record["model"] == "gpt-4"
    assert record["operation_type"] == "completion"
    assert record["input_tokens"] == 5
    assert record["output_tokens"] == 10
    assert record["success"] is True

@pytest.mark.asyncio
@patch('aicore.llm.providers.base_provider.LlmBaseProvider.acompletion_fn')
async def test_operation_tracking_during_acompletion(mock_acompletion, tmp_path):
    """Test that operations are properly tracked during async completion calls."""
    # Setup
    mock_response = MagicMock(
        usage=MagicMock(prompt_tokens=5, completion_tokens=10),
        choices=[MagicMock(message=MagicMock(content="Test async response"))]
    )
    mock_acompletion.return_value = mock_response
    
    storage_dir = str(tmp_path / "observability_test_async")
    storage = OperationStorage(storage_dir=storage_dir)
    
    config = LlmConfig(provider="openai", api_key="test_key", model="gpt-4")
    provider = LlmBaseProvider(config=config)
    provider.collector = LlmOperationCollector(storage_callback=storage.store_record)
    
    # Mock the normalize_fn to handle our mock response
    provider.normalize_fn = lambda x: x.choices
    
    # Execute
    await provider.acomplete("Test prompt", stream=False)
    
    # Verify
    records = storage.get_all_records()
    assert not records.is_empty()
    record = records.to_dicts()[0]
    
    assert record["provider"] == "openai"
    assert record["model"] == "gpt-4"
    assert record["operation_type"] == "acompletion"
    assert record["input_tokens"] == 5
    assert record["output_tokens"] == 10
    assert record["success"] is True

# --- Config Integration Tests ---

def test_observability_config():
    """Test ObservabilityConfig initialization and validation."""
    # Test default configuration
    config = ObservabilityConfig()
    assert config.enabled is True
    assert config.dashboard_port == 8050
    assert config.dashboard_host == "127.0.0.1"
    
    # Test custom configuration
    custom_config = ObservabilityConfig(
        enabled=False,
        storage_dir="custom_dir",
        storage_file="custom_file.json",
        dashboard_enabled=False,
        dashboard_port=9000,
        dashboard_host="0.0.0.0"
    )
    
    assert custom_config.enabled is False
    assert custom_config.storage_dir == "custom_dir"
    assert custom_config.storage_file == "custom_file.json"
    assert custom_config.dashboard_enabled is False
    assert custom_config.dashboard_port == 9000
    assert custom_config.dashboard_host == "0.0.0.0"
    
    # Test port validation
    with pytest.raises(ValueError):
        ObservabilityConfig(dashboard_port=80)  # Below 1024
    
    with pytest.raises(ValueError):
        ObservabilityConfig(dashboard_port=70000)  # Above 65535

def test_observability_in_main_config(tmp_path):
    """Test integration of ObservabilityConfig in the main Config class."""
    # Create a test config file
    config_path = tmp_path / "test_config.yml"
    with open(config_path, "w") as f:
        f.write("""
embeddings:
  provider: "openai"
  api_key: "test_key"
  model: "text-embedding-3-small"
llm:
  provider: "openai"
  api_key: "test_key"
  model: "gpt-4"
observability:
  enabled: false
  storage_dir: "test_storage"
  dashboard_port: 9000
        """)
    
    # Load the config
    config = Config.from_yaml(config_path)
    
    # Verify observability config was properly loaded
    assert config.observability is not None
    assert config.observability.enabled is False
    assert config.observability.storage_dir == "test_storage"
    assert config.observability.dashboard_port == 9000
    
    # Test with missing observability section
    config_path_2 = tmp_path / "test_config_2.yml"
    with open(config_path_2, "w") as f:
        f.write("""
embeddings:
  provider: "openai"
  api_key: "test_key"
llm:
  provider: "openai"
  api_key: "test_key"
        """)
    
    # Load the config without observability section
    config_2 = Config.from_yaml(config_path_2)
    
    # Verify default observability config was created
    assert config_2.observability is not None
    assert config_2.observability.enabled is True
    assert config_2.observability.dashboard_port == 8050
    assert config_2.observability.dashboard_host == "127.0.0.1"

# --- Dashboard Component Tests ---

def test_dashboard_initialization():
    """Test basic dashboard initialization."""
    with patch('dash.Dash') as mock_dash:
        mock_app = MagicMock()
        mock_dash.return_value = mock_app
        
        storage = MagicMock(spec=OperationStorage)
        dashboard = ObservabilityDashboard(storage=storage, title="Test Dashboard")
        
        assert dashboard.storage == storage
        assert dashboard.title == "Test Dashboard"
        assert dashboard.app == mock_app
        mock_app.layout.__eq__.assert_called_once()  # Verify layout was set

def test_create_overview_metrics():
    """Test creation of overview metrics."""
    dashboard = ObservabilityDashboard()
    
    # Create test dataframe with Pandas
    import pandas as pd
    test_data = pd.DataFrame({
        'success': [True, True, False],
        'latency_ms': [100, 200, 300]
    })
    
    metrics = dashboard._create_overview_metrics(test_data)
    
    # Check metrics content
    assert len(metrics) == 3  # Three metric cards
    
    # Check total requests
    assert "Total Requests" in str(metrics[0])
    assert "3" in str(metrics[0])
    
    # Check success rate
    assert "Success Rate" in str(metrics[1])
    assert "66.7%" in str(metrics[1])  # 2/3 * 100 = 66.7%
    
    # Check average latency
    assert "Avg. Latency" in str(metrics[2])
    assert "200.00 ms" in str(metrics[2])  # (100 + 200 + 300) / 3 = 200

def test_create_empty_dashboard():
    """Test creation of empty dashboard components."""
    dashboard = ObservabilityDashboard()
    
    empty_components = dashboard._create_empty_dashboard()
    
    # Check components
    metrics, time_series, latency, token_usage, distribution, table_data, table_columns = empty_components
    
    # Check metrics
    assert len(metrics) == 1
    assert "No Data" in str(metrics[0])
    
    # Check empty figures
    assert "No Data Available" in str(time_series)
    assert "No Data Available" in str(latency)
    assert "No Data Available" in str(token_usage)
    assert "No Data Available" in str(distribution)
    
    # Check empty table
    assert table_data == []
    assert len(table_columns) == 1
    assert table_columns[0]["name"] == "No Data"