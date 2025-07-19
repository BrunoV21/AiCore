from pydantic import BaseModel, model_validator
from typing import Optional, List, AsyncGenerator, Literal
from typing_extensions import Self
from asyncio import Queue as AsyncQueue
from datetime import datetime
from loguru import logger
import asyncio
import pytz
import time
import sys
import os

from aicore.const import (
    DEFAULT_LOGS_DIR,
    STREAM_START_TOKEN,
    STREAM_END_TOKEN,
    REASONING_START_TOKEN,
    REASONING_STOP_TOKEN,
    TOOL_CALL_START_TOKEN,
    TOOL_CALL_END_TOKEN
)

SPECIAL_TOKENS = [
    STREAM_START_TOKEN,
    STREAM_END_TOKEN,
    REASONING_START_TOKEN,
    REASONING_STOP_TOKEN,
    TOOL_CALL_START_TOKEN,
    TOOL_CALL_END_TOKEN,
]

SPECIAL_END_TOKENS = [
    STREAM_END_TOKEN,
    REASONING_STOP_TOKEN
]
    
def default_stream_handler(message :str)->str:
    if message in SPECIAL_TOKENS:
        if message in SPECIAL_END_TOKENS:
            print("\n")
        return
    print(message, end="")
    return message

class LogEntry(BaseModel):
    session_id: str = ""
    message: str
    timestamp: Optional[str] = None
    log_type :Literal["chat", "log"] = "chat"

    @model_validator(mode="after")
    def init_timestamp(self) -> Self:
        """Initialize timestamp if not provided"""
        if not self.timestamp:
            self.timestamp = datetime.now(pytz.UTC).isoformat()
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
            colorize=True,
            rotation="00:00",
            retention="7 days",
            enqueue=True,
            serialize=False,
        )

        # Add stdout sink with colorization
        self.logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            colorize=True,
            enqueue=True,
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
        default_stream_handler(message)

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

# Global logger instance
_logger = Logger()