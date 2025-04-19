# Logger

This module provides an asynchronous, session-based logging system using `loguru`, `pydantic`, and `asyncio`.  
It supports both centralized and session-specific logging, enabling fine-grained log management across concurrent components.

## Features

- Central async queue for all logs
- Session-specific async queues
- Automatic timestamping
- Log rotation and retention
- Special token handling for stream/agent systems
- Live stream support via async generators

---

## Directory Structure

Log files are written to the path configured in `DEFAULT_LOGS_DIR`, with daily rotation.

```py
logs_dir = os.path.join(os.getcwd(), DEFAULT_LOGS_DIR)
os.makedirs(logs_dir, exist_ok=True)
```

---

## Special Tokens

Handled tokens include stream start/end and reasoning blocks:

```py
SPECIAL_TOKENS = [STREAM_START_TOKEN, STREAM_END_TOKEN, REASONING_START_TOKEN, REASONING_STOP_TOKEN]
SPECIAL_END_TOKENS = [STREAM_END_TOKEN, REASONING_STOP_TOKEN]
```

Used to customize terminal output formatting.

---

## Stream Handler

```py
def default_stream_handler(message: str) -> str:
```

- Prints message to stdout
- Inserts newline if an "end token" is encountered
- No return for special tokens

---

## LogEntry Model

A `pydantic` model that standardizes log data:

```py
class LogEntry(BaseModel):
    session_id: str
    message: str
    timestamp: Optional[str]
    log_type: Literal["chat", "log"] = "chat"
```

Timestamps are auto-assigned if not provided.

---

## Logger Class

The main logging manager.

### Initialization

```py
_logger = Logger()
```

- Initializes central and session queues
- Adds loguru sinks (file + stdout)
- Sets file rotation and retention

### Logging Configuration

```py
self.logger.add(log_file_path, rotation="00:00", retention="7 days")
self.logger.add(sys.stdout, format="...", colorize=True)
```

---

## Core Methods

### log_chunk_to_queue

```py
async def log_chunk_to_queue(message: str, session_id: str)
```

- Adds a message to the central queue
- Stores a copy in `_temp_storage`
- Prints using `default_stream_handler`

---

### get_all_logs_in_queue

```py
def get_all_logs_in_queue() -> List[LogEntry]
```

Returns a shallow copy of `_temp_storage`, representing all log history currently stored in memory.

---

### distribute

```py
async def distribute(finite: bool = False)
```

- Continuously transfers logs from the central queue to session-specific queues
- Terminates if `finite=True` and the queue is empty

---

### get_session_logs

```py
async def get_session_logs(session_id: str, timeout: Optional[float] = None)
```

Async generator that yields logs for a specific session.

- Creates queue if not present
- Waits indefinitely or until `timeout` (if set)

---

### pop

```py
async def pop(session_id: str, poll_interval: float = 0.1)
```

Yields logs for a given session from the central queue until a `REASONING_STOP_TOKEN` is encountered.

- Buffers unrelated logs temporarily
- Reinserts them into the queue after

---

## Session Metadata

### all_sessions_in_queue

```py
@property
def all_sessions_in_queue -> List[str]
```

Returns unique session IDs based on `_temp_storage`.

---

### all_sessions_in_queues

```py
@property
def all_sessions_in_queues -> List[str]
```

Returns all currently active session-specific queues.

---

## Error Handling

All async methods handle:

- `asyncio.CancelledError` (gracefully cancels tasks)
- General exceptions (logged via `loguru`)
- Empty queues (using timeouts and sleeps)

---

## Example Usage

```py
await _logger.log_chunk_to_queue("message", session_id="abc123")

async for log in _logger.get_session_logs("abc123"):
    print(log)
```

Use `.distribute()` in the background to ensure logs are routed to appropriate session queues.

---

## Notes

- Designed for systems with concurrent sessions (e.g. AI agents, chat apps)
- Can be extended to include filtering, log level overrides, or streaming endpoints
- Compatible with production environments using `asyncio` and multi-user contexts

---

## Global Access

```py
from aicore.logger import _logger
```
