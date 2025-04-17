
# Observability Dashboard Example

This guide demonstrates how to use the AiCore observability dashboard to monitor and analyze LLM operations.

## Prerequisites

- AiCore installed (`pip install aicore`)
- Python 3.10+
- Optional: Polars for advanced data analysis (`pip install polars`)

## Basic Usage

### 1. Initialize LLM with Observability

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

# Configure LLM with observability enabled by default
config = LlmConfig(
    provider="openai",
    api_key="your_api_key",
    model="gpt-4o"
)

llm = Llm(config=config)
```

### 2. Make Some LLM Calls

```python
# These calls will automatically be tracked
response1 = llm.complete("Explain quantum computing")
response2 = await llm.acomplete("Write a poem about AI")
```

### 3. Access Collected Data

```python
from aicore.observability.collector import LlmOperationCollector

# Get all operations as a list of dictionaries
operations = LlmOperationCollector.get_operations()

# Get operations for a specific session
session_ops = LlmOperationCollector.get_operations(session_id=llm.session_id)
```

## Advanced Analysis with Polars

For more powerful analysis, use Polars:

```python
import polars as pl

# Get operations as a Polars DataFrame
df = LlmOperationCollector.polars_from_db()

# Example analyses:
print("Token usage by provider:")
print(df.group_by("provider").agg(
    pl.col("input_tokens").sum().alias("total_input_tokens"),
    pl.col("output_tokens").sum().alias("total_output_tokens")
))

print("\nAverage latency by model:")
print(df.group_by("model").agg(
    pl.col("latency_ms").mean().alias("avg_latency_ms")
))
```

## Visualizing Data

Create simple visualizations using the collected data:

```python
import matplotlib.pyplot as plt

df = LlmOperationCollector.polars_from_db()

# Plot latency distribution
latency_data = df["latency_ms"].to_list()
plt.hist(latency_data, bins=20)
plt.title("LLM Operation Latency Distribution")
plt.xlabel("Latency (ms)")
plt.ylabel("Frequency")
plt.show()
```

## Saving and Loading Data

```python
# Save operations to JSON file
LlmOperationCollector.save_to_json("llm_operations.json")

# Load operations from JSON file
loaded_ops = LlmOperationCollector.load_from_json("llm_operations.json")
```

## Custom Dashboard Example

Here's a complete example of building a simple dashboard:

```python
from aicore.observability.collector import LlmOperationCollector
import polars as pl
import matplotlib.pyplot as plt

def generate_dashboard():
    # Get data
    df = LlmOperationCollector.polars_from_db()
    
    # Create figure
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Token usage by provider
    plt.subplot(2, 2, 1)
    token_usage = df.group_by("provider").agg(
        pl.col("input_tokens").sum().alias("input"),
        pl.col("output_tokens").sum().alias("output")
    ).to_pandas()
    token_usage.plot(kind="bar", stacked=True, ax=plt.gca())
    plt.title("Token Usage by Provider")
    
    # Plot 2: Cost over time
    plt.subplot(2, 2, 2)
    df.with_columns(
        pl.col("timestamp").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S.%fZ")
    ).sort("timestamp").to_pandas().plot(
        x="timestamp", y="cost", ax=plt.gca()
    )
    plt.title("Cost Over Time")
    
    # Plot 3: Success rate
    plt.subplot(2, 2, 3)
    success_rate = df.group_by("provider").agg(
        (pl.col("error_message").is_null().mean().alias("success_rate")
    ).to_pandas()
    success_rate.plot(kind="bar", ax=plt.gca())
    plt.title("Success Rate by Provider")
    
    # Plot 4: Latency distribution
    plt.subplot(2, 2, 4)
    df["latency_ms"].to_pandas().plot(kind="hist", bins=20, ax=plt.gca())
    plt.title("Latency Distribution")
    
    plt.tight_layout()
    plt.show()

generate_dashboard()
```

## Key Metrics to Track

The observability system automatically tracks:
- Operation timestamps
- Provider and model used
- Input/output token counts
- Cost calculations
- Latency measurements
- Error messages (if any)
- Session and workspace context
- Custom metadata (via extras)

## Configuration Options

You can configure observability behavior:

```python
from aicore.observability.collector import LlmOperationCollector

# Change storage location
LlmOperationCollector.set_storage_path("custom_observability_data")

# Disable collection for specific provider
llm.provider.disable_collection()

# Set custom metadata for all operations
llm.extras = {"environment": "production", "app_version": "1.2.3"}
```

## Troubleshooting

If data isn't appearing in the dashboard:
1. Verify the collector is enabled (`llm.provider.collector.is_enabled`)
2. Check the storage directory exists and is writable
3. Ensure operations are being completed (check for errors)
4. Verify you're querying the correct session ID if filtering

For more advanced use cases, refer to the [Observability Documentation](../observability/overview.md).