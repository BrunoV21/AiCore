# Env file with examples for SQL integration

```bash
# PostgreSQL
CONNECTION_STRING="postgresql://user:password@localhost/dbname"
ASYNC_CONNECTION_STRING = "postgresql+asyncpg://user:password@localhost/dbname"

# MySQL
CONNECTION_STRING="mysql://user:password@localhost/dbname"
ASYNC_CONNECTION_STRING = "mysql+aiomysql://user:password@localhost/dbname"

# SQLite (file-based)
CONNECTION_STRING="sqlite:///path/to/database.db"
ASYNC_CONNECTION_STRING = "sqlite+aiosqlite:///path/to/database.db"

# Microsoft SQL Server
CONNECTION_STRING="mssql+pyodbc://user:password@server/dbname?driver=SQL+Server"
ASYNC_CONNECTION_STRING = "mssql+aioodbc://user:password@server/dbname?driver=SQL+Server"
```