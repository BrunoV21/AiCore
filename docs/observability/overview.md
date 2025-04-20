
# Observability Overview

The AiCore observability system provides comprehensive monitoring, analytics, and visualization for LLM operations across all supported providers. This documentation covers the key components and features of the observability system.

## Key Features

- **Operation Tracking**: Records all LLM operations (completions, embeddings) with full context
- **Performance Metrics**: Tracks latency, token usage, success rates, and error patterns
- **Cost Analysis**: Calculates and tracks API costs by provider/model/operation
- **Agent Monitoring**: Correlates operations with agents, sessions, and workspaces
- **Multi-storage Support**: JSON files for local development and SQL databases for production
- **High-performance Analytics**: Polars integration for efficient data analysis

## Core Components

### 1. Operation Collector

The [`LlmOperationCollector`](./collector.md) is the central component that captures and stores all LLM operation data. It provides:

- Both synchronous and asynchronous recording methods
- Automatic schema management for database storage
- Flexible storage backends (JSON files or SQL databases)
- Built-in cost calculation based on provider pricing

```python
from aicore.observability import LlmOperationCollector

# Initialize with custom storage path
collector = LlmOperationCollector(storage_path="/custom/path/operations.json")
```

### 2. Dashboard

The interactive [Observability Dashboard](./dashboard.md) provides:

- Real-time monitoring of LLM operations
- Historical trend analysis
- Cost breakdowns by team/project/model
- Customizable views and filters

```python
from aicore.observability import ObservabilityDashboard

# Launch dashboard with custom port
dashboard = ObservabilityDashboard(port=8080)
dashboard.run_server()
```

### 3. Data Analysis Tools

- **[SQL Integration](./sql.md)**: Query operation data using standard SQL
- **[Polars Integration](./polars.md)**: High-performance DataFrame operations
- **Custom Export**: Export data to CSV, Parquet, or other formats

## Data Model

The observability system tracks:

1. **Operation Metadata**:
   - Provider, model, and endpoint used
   - Timestamps and duration
   - Status (success/failure)

2. **Performance Metrics**:
   - Latency at various stages
   - Token counts (input/output/total)
   - Retry attempts

3. **Contextual Information**:
   - Session and workspace identifiers
   - Agent/action context
   - Custom tags and metadata

## Getting Started
Included a connection or async connection string in your [.env file](./env-example.md)

For detailed information about each component, see the dedicated documentation pages:

- [Operation Collector](./collector.md)
- [Dashboard](./dashboard.md)
- [SQL Integration](./sql.md)
- [Polars Integration](./polars.md)