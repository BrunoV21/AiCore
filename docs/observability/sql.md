
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

For more advanced analytics capabilities, see the [Polars Integration](./polars.md) documentation.