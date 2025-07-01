# Observability Dashboard Example

This guide demonstrates how to use the AiCore observability dashboard to monitor and analyze LLM operations.

## Prerequisites

- AiCore installed (`pip install core-for-ai`)
- Python 3.10+
- Optional: Polars for advanced data analysis (`pip install polars`)
- Optional: Matplotlib for visualizations (`pip install matplotlib`)

## Basic Usage

### 1. Initialize LLM with Observability

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

# Configure LLM with observability enabled by default
config = LlmConfig(
    provider="openai",
    api_key="your_api_key",
    model="gpt-4",
    observability={
        "enabled": True,
        "storage_path": "llm_metrics.db"
    }
)

llm = Llm(config=config)
```

### 2. Make Some LLM Calls

```python
# These calls will automatically be tracked
response1 = llm.complete("Explain quantum computing")
response2 = await llm.acomplete("Write a poem about AI")

# Track custom metadata
llm.extras = {
    "user_id": "user123",
    "application": "customer_support"
}
```

## Advanced Analysis with Polars

For more powerful analysis, use Polars:

```python
import polars as pl
from aicore.observability.collector import LlmOperationCollector

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
    pl.col("latency_ms").mean().alias("avg_latency_ms"),
    pl.col("latency_ms").std().alias("std_latency_ms")
))

# Filter recent operations
recent_ops = df.filter(
    pl.col("timestamp") > (pl.datetime.now() - pl.duration(days=1))
```

## Visualizing Data

Create visualizations using the collected data:

```python
import matplotlib.pyplot as plt
import seaborn as sns

df = LlmOperationCollector.polars_from_db().to_pandas()

# Plot latency distribution
plt.figure(figsize=(10, 6))
sns.histplot(data=df, x="latency_ms", bins=30, kde=True)
plt.title("LLM Operation Latency Distribution")
plt.xlabel("Latency (ms)")
plt.ylabel("Frequency")
plt.show()

# Plot token usage by model
plt.figure(figsize=(12, 6))
sns.barplot(
    data=df.groupby(["provider", "model"]).agg({
        "input_tokens": "sum",
        "output_tokens": "sum"
    }).reset_index(),
    x="model",
    y="input_tokens",
    hue="provider"
)
plt.title("Input Token Usage by Model and Provider")
plt.xticks(rotation=45)
plt.show()
```

## Custom Dashboard Example

Here's a complete example of building a simple dashboard:

```python
from aicore.observability.collector import LlmOperationCollector
import polars as pl
import matplotlib.pyplot as plt
import seaborn as sns

def generate_dashboard(session_id: str = None):
    # Get data with optional session filter
    df = LlmOperationCollector.polars_from_db()
    if session_id:
        df = df.filter(pl.col("session_id") == session_id)
    
    # Convert to pandas for visualization
    df_pd = df.to_pandas()
    
    # Create figure
    plt.figure(figsize=(18, 12))
    
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
        (pl.col("error_message").is_null().mean() * 100
    ).to_pandas()
    success_rate.plot(kind="bar", ax=plt.gca())
    plt.title("Success Rate by Provider (%)")
    
    # Plot 4: Latency distribution
    plt.subplot(2, 2, 4)
    sns.boxplot(data=df_pd, x="provider", y="latency_ms")
    plt.title("Latency Distribution by Provider")
    plt.yscale("log")
    
    plt.tight_layout()
    plt.show()

generate_dashboard()
```

## Key Metrics Tracked

The observability system automatically tracks:
- Operation timestamps
- Provider and model used
- Input/output token counts
- Cost calculations
- Latency measurements
- Error messages (if any)
- Session and workspace context
- Custom metadata (via extras)
- API response status codes
- Retry attempts
- Model parameters (temperature, max_tokens)

## Advanced Configuration

```python
from aicore.observability.collector import LlmOperationCollector

# Change storage location and retention
LlmOperationCollector.configure(
    storage_path="custom_metrics.db",
    retention_days=30  # Keep data for 30 days
)

# Enable/disable specific tracking
LlmOperationCollector.set_tracking_options(
    track_tokens=True,
    track_latency=True,
    track_errors=True,
    track_costs=True
)

# Set custom metadata for all operations
llm.extras = {
    "environment": "production",
    "app_version": "1.2.3",
    "deployment_region": "us-west-1"
}
```

## Integration with FastAPI

Example of integrating observability with FastAPI:

```python
from fastapi import FastAPI, Request
from aicore.llm import Llm
from aicore.observability.collector import LlmOperationCollector

app = FastAPI()
llm = Llm.from_config(...)

@app.middleware("http")
async def add_request_context(request: Request, call_next):
    llm.session_id = request.headers.get("X-Session-ID", "default")
    llm.extras = {
        "endpoint": request.url.path,
        "method": request.method
    }
    response = await call_next(request)
    return response

@app.get("/analyze")
async def analyze_metrics():
    df = LlmOperationCollector.polars_from_db()
    return {
        "total_requests": len(df),
        "avg_latency": df["latency_ms"].mean(),
        "error_rate": df["error_message"].is_null().mean()
    }
```

## Troubleshooting

If data isn't appearing in the dashboard:
1. Verify the collector is enabled (`llm.provider.collector.is_enabled`)
2. Check the storage directory exists and is writable
3. Ensure operations are being completed (check for errors)
4. Verify you're querying the correct session ID if filtering
5. Check the retention policy hasn't purged older data

For more advanced use cases, refer to the [Observability Documentation](../observability/overview.md).