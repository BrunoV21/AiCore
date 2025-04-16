
# SQL Integration

The AiCore observability system provides seamless SQL database integration for storing and querying LLM operation metrics with full SQLAlchemy compatibility.

## Features

- **Multi-database Support**: Works with PostgreSQL, MySQL, SQLite, and other SQLAlchemy-compatible databases
- **Schema Management**: Automatic table creation and schema migrations
- **Sync & Async Support**: Both synchronous and asynchronous operations
- **Advanced Query Capabilities**: Filter, aggregate, and join metrics efficiently
- **Polars Integration**: Query results can be directly loaded as Polars DataFrames

## Configuration

Configure your database connection via environment variables or directly in code:

### Environment Variables
```bash
# For synchronous connections
export CONNECTION_STRING="postgresql://user:password@localhost/dbname"

# For async connections 
export ASYNC_CONNECTION_STRING="postgresql+asyncpg://user:password@localhost/dbname"
```

### Programmatic Configuration
```python
from aicore.observability.collector import LlmOperationCollector

collector = LlmOperationCollector(
    db_uri="postgresql://user:password@localhost/dbname",
    async_db_uri="postgresql+asyncpg://user:password@localhost/dbname"
)
```

## Database Schema

The system uses a normalized schema with three main tables:

### `llm_sessions` Table
- `session_id` (Primary Key, UUID)
- `workspace` (String)
- `agent_id` (String)
- `created_at` (Timestamp)
- `metadata` (JSON)

### `llm_operations` Table  
- `operation_id` (Primary Key, UUID)
- `session_id` (Foreign Key)
- `action_id` (String)
- `timestamp` (Timestamp)
- `operation_type` (String)
- `provider` (String)
- `model` (String)
- `input_tokens` (Integer)
- `output_tokens` (Integer)
- `latency_ms` (Integer)
- `cost` (Float)
- `status` (String)
- `error_message` (String)
- `extras` (JSON)

### `llm_messages` Table
- `message_id` (Primary Key, UUID)
- `operation_id` (Foreign Key)
- `role` (String)
- `content` (Text)
- `sequence_number` (Integer)

## Usage Examples

### Basic Query
```python
from aicore.observability.collector import LlmOperationCollector

# Get all data as Polars DataFrame
df = LlmOperationCollector.polars_from_db()

# Get data with specific filters
filtered_df = LlmOperationCollector.polars_from_db(
    start_date="2023-01-01",
    end_date="2023-12-31",
    provider="openai",
    min_tokens=100
)
```

### Advanced Queries

#### Cost Analysis by Provider
```python
from aicore.observability.collector import query_db

results = query_db(
    """
    SELECT 
        provider,
        SUM(cost) as total_cost,
        COUNT(*) as request_count,
        AVG(latency_ms) as avg_latency
    FROM llm_operations
    GROUP BY provider
    ORDER BY total_cost DESC
    """
)
```

#### Session Analysis
```python
results = query_db(
    """
    SELECT 
        s.workspace,
        s.agent_id,
        COUNT(o.operation_id) as operation_count,
        SUM(o.cost) as total_cost
    FROM llm_sessions s
    JOIN llm_operations o ON s.session_id = o.session_id
    GROUP BY s.workspace, s.agent_id
    """
)
```

#### Error Analysis
```python
error_df = LlmOperationCollector.polars_from_db(
    """
    SELECT 
        provider,
        model,
        error_message,
        COUNT(*) as error_count
    FROM llm_operations
    WHERE status = 'error'
    GROUP BY provider, model, error_message
    ORDER BY error_count DESC
    """
)
```

## Best Practices

1. **Indexing**: For production deployments, add indexes on frequently queried columns:
   ```sql
   CREATE INDEX idx_llm_operations_timestamp ON llm_operations(timestamp);
   CREATE INDEX idx_llm_operations_provider ON llm_operations(provider);
   ```

2. **Partitioning**: For high-volume systems, consider partitioning by date range.

3. **Connection Pooling**: Configure appropriate connection pool sizes in your database URL:
   ```
   postgresql://user:password@localhost/dbname?pool_size=20&max_overflow=10
   ```

4. **Backup Strategy**: Implement regular database backups for your observability data.

For more advanced analytics capabilities, see the [Polars Integration](./polars.md) documentation.