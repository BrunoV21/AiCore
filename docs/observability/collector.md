
# LLM Operation Collector

The `LlmOperationCollector` is a core component of AiCore's observability system that tracks and stores detailed metrics about LLM operations. It provides comprehensive insights into API usage, performance, and costs.

## Key Features

- **Multi-storage support**: JSON files and SQL databases
- **Async/Sync recording**: `record_completion()` and `arecord_completion()`
- **Polars integration**: Efficient analytics on operation data
- **Automatic schema management**: Handles database table creation
- **Cost tracking**: Automatic cost calculation per request
- **Agent monitoring**: Track operations by agent/action
- **Schema extensions**: Add custom metrics via `extras` field

## Data Collection

The collector tracks the following metrics for each operation:

| Metric | Description |
|--------|-------------|
| Request metadata | Model, parameters, messages |
| Response data | Completion content, finish reason |
| Token counts | Prompt and completion tokens |
| Latency | Request duration in milliseconds |
| Costs | Calculated based on provider pricing |
| Errors | Any encountered errors with stack traces |
| Context | Agent, session, and workspace identifiers |

## Basic Usage

### Initialization

```python
from aicore.observability import LlmOperationCollector

# Basic initialization with default storage
collector = LlmOperationCollector()

# Custom storage configuration
collector = LlmOperationCollector()
```

### Recording Operations

```python
# Synchronous recording
collector.record_completion(
    completion_args={
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7
    },
    operation_type="completion",
    provider="openai",
    response="Hi there!",
    latency_ms=1200,
    extras={"custom_metric": "value"}  # Optional additional data
)

# Asynchronous recording
await collector.arecord_completion(...)  # Same parameters as above
```

## Data Storage Options

### JSON File Storage

```python
# Save operations to JSON file
collector = LlmOperationCollector()

# Load data into Polars DataFrame
df = LlmOperationCollector.polars_from_file()

# Filter operations
df = df.filter(
    (pl.col("provider") == "openai") &
    (pl.col("latency_ms") < 1000)
)
```

### SQL Database

```python 
# Initialize with SQL database
collector = LlmOperationCollector()

# Query database with Polars
df = LlmOperationCollector.polars_from_db(
    start_date="2023-01-01",
    end_date="2023-12-31",
    provider="openai",
    min_tokens=10
)

# Available filters:
# - start_date/end_date: Date range filtering
# - provider: Filter by provider name
# - operation_type: Filter by operation type
# - min_tokens/max_tokens: Filter by token count
# - min_latency/max_latency: Filter by latency
```

## Advanced Usage

### Custom Metrics

```python
# Add custom metrics to operations
collector.record_completion(
    ...,
    extras={
        "user_id": "12345",
        "project": "marketing",
        "classification": "support"
    }
)

# Query custom metrics
df = collector.polars_from_db()
df = df.filter(pl.col("extras").struct.field("project") == "marketing")
```

### Database Schema Management

```python
# Create tables manually (automatic by default)
collector.create_tables()
```

For more examples, see the [Observability Examples](../examples/README.md).