
## AiCore Logging Module

This document explains the logging module of the AiCore Project, detailing its operation, configuration, and integration with the LLM module to support real-time streaming of log output.

## Overview

The AiCore logging module, implemented in `aicore/logger.py`, utilizes Loguru to capture, record, and distribute logs generated during LLM operations. It supports:

- **File-based Logging:** Logs are saved to files (with daily rotation and configurable retention).
- **Console Logging:** Real-time log streaming to the console with colorization.
- **Session-specific Queues:** Each LLM operation is associated with a session ID, enabling targeted retrieval and streaming of log entries.

## Key Components

### Logger Initialization

The logger is initialized with the following features:

- **Log Directory:** A default directory (e.g., "logs") is created to store log files.
- **File Rotation:** Log files are rotated daily, and retention policies ensure that old logs are purged as configured.
- **Console Handler:** Logs are also streamed to the standard output with clear formatting and color coding.
  
### LogEntry Model

Every log entry is encapsulated in a data structure (conceptually represented by `LogEntry`) which includes the following fields:

- **session_id:** Uniquely identifies the session for the log entry.
- **message:** The text message of the log.
- **timestamp:** The exact time the log entry was recorded.

### Stream Handler

The default stream handler (`default_stream_handler`) is responsible for:

- Filtering special tokens (e.g., tokens indicating the start/end of a stream or special markers for reasoning segments).
- Immediately outputting stream tokens to the console, ensuring minimal delay in logging stream outputs.
  
## Integration with the LLM Module

The logging module is tightly integrated with the LLM module to support real-time streaming of log outputs during operations. The integration workflow is as follows:

1. **LLM Operation:** When an LLM operation is initiated, log streaming is activated.
2. **Token Streaming:** As the LLM generates tokens (e.g., during the `complete` method call with streaming enabled), each token chunk is sent to the logger.
3. **Session-specific Logging:** Tokens are tagged with a session ID so that logs can be filtered and retrieved on a per-session basis.
4. **Retrieval:** Clients and monitoring tools can asynchronously retrieve logs for a given session using functions like `_logger.get_session_logs(session_id)`.

## Usage Example

Below is a simple Python snippet illustrating how to log and asynchronously retrieve streaming logs associated with a specific LLM session:

```python
from aicore.logger import _logger
import asyncio

async def log_and_retrieve():
    session_id = "session_123"
    
    # Simulate logging a chunk of an LLM streaming operation
    await _logger.log_chunk_to_queue("Processing response chunk...", session_id)
    
    # Retrieve and print all log entries for the session with a timeout of 2 seconds
    async for log in _logger.get_session_logs(session_id, timeout=2.0):
        print("Log:", log)

asyncio.run(log_and_retrieve())
```

## Configuration

The logging module can be customized via several configuration options:

- **Log Directory:** Controlled by the `DEFAULT_LOGS_DIR` variable (default: "logs").
- **Rotation & Retention:** Configurations in the logger setup determine file naming conventions, rotation intervals, and the retention period.
- **Stream Filter:** The function `default_stream_handler` can be adjusted to modify filtering behavior for special tokens.

## Future Improvements

Potential enhancements to the logging module include:

- Fine-tuning log levels and formats for more granular control.
- Expanded integration with external monitoring and alerting systems.
- Improved session management and more advanced log filtering capabilities.

---
*This documentation provides an initial overview of the AiCore Logging Module. Future updates will include additional configuration details and usage patterns based on community feedback and evolving project requirements.*