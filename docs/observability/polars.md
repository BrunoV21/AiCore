
# Polars Integration

The AiCore observability system provides seamless integration with [Polars](https://www.pola.rs/) for high-performance data analysis of LLM operation metrics.

## Key Features

- **High-performance analytics**: Leverage Polars' optimized DataFrame operations
- **SQL integration**: Query database results directly as Polars DataFrames
- **File-based analysis**: Load JSON operation history into Polars
- **Time-series analysis**: Built-in date/time handling for temporal analysis
- **Cost analysis**: Calculate usage costs across providers and models
- **Performance metrics**: Analyze latency, throughput, and error rates

## Basic Usage

### From Database

```python
from aicore.observability.collector import LlmOperationCollector
import polars as pl

# Get all data as Polars DataFrame
df = LlmOperationCollector.polars_from_db()
```

### From JSON Files

```python
from aicore.observability.collector import LlmOperationCollector

# Load from default storage path
df = LlmOperationCollector.polars_from_file()

# Specify custom path
custom_df = LlmOperationCollector.polars_from_file("/path/to/operations.json")
```

## Common Analysis Patterns

### Time-Series Analysis

```python
# Group by day and count requests
daily_counts = (
    df.with_columns(pl.col("timestamp").dt.truncate("1d").alias("day"))
    .group_by("day")
    .agg(pl.len().alias("count"))
)
```

### Performance Metrics

```python
# Calculate average latency by provider
latency_by_provider = df.group_by("provider").agg(
    pl.col("latency_ms").mean().alias("avg_latency"),
    pl.col("latency_ms").median().alias("median_latency"),
    pl.col("latency_ms").std().alias("latency_stddev")
)
```

### Cost Analysis

```python
# Calculate total cost by model
cost_analysis = df.group_by(["provider", "model"]).agg(
    pl.col("cost").sum().alias("total_cost"),
    pl.col("completion_tokens").sum().alias("total_tokens")
)
```

## Advanced Usage

### Joining with External Data

```python
# Join with model metadata
model_metadata = pl.read_csv("model_metadata.csv")
enriched_df = df.join(
    model_metadata,
    left_on="model",
    right_on="model_name",
    how="left"
)
```

### Writing Analysis Results

```python
# Save analysis results
latency_by_provider.write_csv("latency_report.csv")
cost_analysis.write_parquet("cost_analysis.parquet")
```

## Performance Tips

1. Use `.lazy()` for complex operations to optimize query planning
2. Filter data early in the pipeline with `.filter()`
3. Use `.select()` to only load needed columns
4. For large datasets, consider chunked processing

```python
# Optimized analysis example
(df.lazy()
    .filter(pl.col("timestamp") > "2023-01-01")
    .select(["provider", "model", "latency_ms", "cost"])
    .group_by(["provider", "model"])
    .agg([
        pl.col("latency_ms").mean(),
        pl.col("cost").sum()
    ])
    .collect())
```

For more information, see the [Polars documentation](https://pola-rs.github.io/polars/py-polars/html/reference/).