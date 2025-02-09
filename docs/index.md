# AI Core Documentation

Welcome to the AI Core documentation! This guide will help you understand and use the AI Core project effectively.

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Logging](#logging)
6. [Contributing](#contributing)
7. [License](#license)

## Introduction

AI Core is a comprehensive framework designed to facilitate the integration and management of various AI models and embeddings. It provides a unified interface for configuring and utilizing different AI providers and models.

## Installation

To install AI Core, follow these steps:

1. Clone the repository:
    ```sh
    git clone https://github.com/your-repo/ai-core.git
    cd ai-core
    ```

2. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Configuration

AI Core uses a configuration file to manage settings for different AI providers and models. The configuration is loaded from a YAML file.

### Configuration Classes

#### LlmConfig

The `LlmConfig` class is used to configure Large Language Models (LLMs).

```python
from pydantic import BaseModel, field_validator
from typing import Literal, Optional, Union

class LlmConfig(BaseModel):
    provider: Literal["gemini", "groq", "mistral", "nvidia", "openai", "openrouter"]
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0
    max_tokens: int = 12000
    reasoner: Union["LlmConfig", None] = None

    @field_validator("temperature")
    @classmethod
    def ensure_temperature_lower_than_unit(cls, temperature: float) -> float:
        assert 0 <= temperature <= 1, "temperature should be between 0 and 1"
        return temperature

    @field_validator("reasoner", mode="after")
    @classmethod
    def ensure_valid_reasoner(cls, reasoner: "LlmConfig") -> "LlmConfig":
        assert reasoner.provider in SUPPORTED_REASONER_PROVIDERS, f"{reasoner.provider} is not supported as a reasoner provider. Supported providers are {SUPPORTED_REASONER_PROVIDERS}"
        assert reasoner.model in SUPPORTED_REASONER_MODELS, f"{reasoner.model} is not supported as a reasoner model. Supported models are {SUPPORTED_REASONER_MODELS}"
        return reasoner
```

#### EmbeddingsConfig

The `EmbeddingsConfig` class is used to configure embeddings.

```python
from pydantic import BaseModel
from typing import Literal, Optional

class EmbeddingsConfig(BaseModel):
    provider: Literal["gemini", "groq", "mistral", "nvidia", "openai"]
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None
```

### Loading Configuration

The `Config` class is the main configuration class for the AI core.

```python
from pydantic import BaseModel
from typing import Optional, Union
from pathlib import Path
import os
import yaml

class Config(BaseModel):
    embeddings: EmbeddingsConfig = None
    llm: LlmConfig = None

    @classmethod
    def from_yaml(cls, config_path: Optional[Union[str, Path]] = None) -> "Config":
        if config_path is None:
            config_path = os.getenv("CONFIG_PATH") or DEFAULT_CONFIG_PATH
        config_path = Path(config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}. Please ensure the file exists and the path is correct.")

        with open(config_path, "r") as _file:
            yaml_config = yaml.safe_load(_file)

        return cls(**yaml_config)
```

## Usage

To use AI Core, follow these steps:

1. Load the configuration:
    ```python
    config = Config.from_yaml("path/to/config.yaml")
    ```

2. Use the configured models:
    ```python
    llm_model = config.llm
    embeddings_model = config.embeddings
    ```

## Logging

AI Core includes a robust logging system to track and debug the documentation generation process.

### Logger Class

The `Logger` class is responsible for logging.

```python
from loguru import logger
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, model_validator
import os
import asyncio
from asyncio import Queue as AsyncQueue

class LogEntry(BaseModel):
    session_id: str = ""
    message: str
    timestamp: Optional[str] = None

    @model_validator(mode="after")
    def init_timestamp(self) -> Self:
        """Initialize timestamp if not provided"""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        return self

class Logger:
    def __init__(self, logs_dir=DEFAULT_LOGS_DIR):
        """
        Initialize the logger object.
        :param logs_dir: Directory where log files will be stored.
        """
        self.logs_dir = os.path.join(os.getcwd(), logs_dir)
        os.makedirs(self.logs_dir, exist_ok=True)

        # Loguru setup
        log_file_path = os.path.join(self.logs_dir, "{time:YYYY-MM-DD}.log")
        self.logger = logger
        self.logger.remove()  # Remove default logging to stderr
        self.logger.add(
            log_file_path,
            format="{time} {level} {message}",
            rotation="00:00",
            retention="7 days",
            enqueue=True,
            serialize=False,
        )

        # Central log queue (now async)
        self.queue = AsyncQueue()
        # Session-based queues (now async)
        self.session_queues = {}
        self._temp_storage = []

    @property
    def all_sessions_in_queue(self) -> List[str]:
        all_sessions = list(set([
            entry.session_id for entry in self.get_all_logs_in_queue()
        ]))
        all_sessions.sort()
        return all_sessions

    @property
    def all_sessions_in_queues(self) -> List[str]:
        return list(self.session_queues.keys())

    async def log_chunk_to_queue(self, message: str, session_id: str):
        """
        Log a message to the central queue and the log file.
        :param message: Message to log.
        :param session_id: Unique session ID for the log.
        """
        log_entry = LogEntry(
            session_id=session_id,
            message=message
        )
        await self.queue.put(log_entry)
        self._temp_storage.append(log_entry)
        print(message, end="")

    def get_all_logs_in_queue(self) -> List[LogEntry]:
        """
        Retrieve all logs currently in the central log queue without removing them.
        :return: List of all log entries in the central queue.
        """
        return self._temp_storage.copy()

    async def distribute(self, finite: bool = False):
        """
        Distribute logs from the central queue to session-specific queues.
        Runs continuously in the background unless finite=True.

        Args:
            finite (bool): If True, method will return when queue is empty
        """
        while True:
            try:
                # Wait for the next log entry
                log = await self.queue.get()

                session_id = log.session_id
                # Create session queue if it doesn't exist
                if session_id not in self.session_queues:
                    self.session_queues[session_id] = AsyncQueue()

                # Distribute to session-specific queue
                await self.session_queues[session_id].put(log)
                self.queue.task_done()

                if self.queue.empty() and finite:
                    return

            except asyncio.CancelledError:
                logger.info("Distribute task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in distribute: {str(e)}")
                await asyncio.sleep(0.1)

    async def get_session_logs(self, session_id: str, timeout: Optional[float] = None) -> AsyncGenerator[str, None]:
        """
        Retrieve logs from a session-specific queue.

        Args:
            session_id (str): The session ID to get logs for
            timeout (Optional[float]): Maximum time to wait for new logs in seconds
                                     None means wait indefinitely

        Yields:
            str: Log messages for the specified session
        """
        if session_id not in self.session_queues:
            if session_id not in self.session_queues:
                self.session_queues[session_id] = AsyncQueue()

        queue = self.session_queues[session_id]
        start_time = time.time()

        while True:
            try:
                if timeout is not None and time.time() - start_time > timeout:
                    logger.debug(f"Timeout reached for session {session_id}")
                    break

                # Try to get log from the session queue
                try:
                    log: LogEntry = await asyncio.wait_for(
                        queue.get(),
                        timeout=0.1 if timeout is not None else None
                    )
                except asyncio.TimeoutError:
                    continue

                queue.task_done()
                yield log.message

            except asyncio.CancelledError:
                logger.info(f"Session log retrieval cancelled for {session_id}")
                break
            except Exception as e:
                logger.error(f"Error retrieving session logs: {str(e)}")
                await asyncio.sleep(0.1)

    async def pop(self, session_id: str, poll_interval: float = 0.1):
        """
        Asynchronously retrieves logs for a given session ID.
        :param session_id: Unique session ID to filter logs.
        :param poll_interval: Time in seconds to wait before checking the queue again.
        :param timeout: Maximum time in seconds to wait since the first log was extracted.
            If None, no timeout is applied.
        """
        temp_storage = []
        last_log_content = None
        last_log_time = None  # Initialize as None; start counting after the first log

        while True:
            try:
                # Try to get an item from the queue
                log: LogEntry = await self.queue.get()

                if log.session_id == session_id:
                    self.queue.task_done()
                    # Start the timer after the first log is extracted
                    if last_log_time is None:
                        last_log_time = time.time()
                    last_log_content = log.message
                    yield log.message
                    if REASONING_STOP_TOKEN in last_log_content:
                        break

                else:
                    temp_storage.append(log)

                # Put back non-matching logs
                for stored_log in temp_storage:
                    await self.queue.put(stored_log)
                temp_storage.clear()

            except asyncio.CancelledError:
                # Handle cancellation gracefully
                if temp_storage:
                    for stored_log in temp_storage:
                        await self.queue.put(stored_log)
                break
            except Exception as e:
                logger.error(f"Error in pop: {str(e)}")
                await asyncio.sleep(poll_interval)
```

## Contributing

We welcome contributions from the community! To contribute, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and ensure all tests pass.
4. Submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.