from pydantic import BaseModel, model_validator
from typing import Optional, List, Self
from asyncio import Queue as AsyncQueue
from datetime import datetime
from loguru import logger
import asyncio
import time
import os

from aicore.const import DEFAULT_LOGS_DIR, REASONING_STOP_TOKEN

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
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)

        # Loguru setup
        log_file_path = os.path.join(self.logs_dir, "{time:YYYY-MM-DD}.log")
        logger.remove()  # Remove default logging to stderr
        logger.add(
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

    async def distribute(self):
        """
        Distribute logs from the central queue to session-specific queues.
        Runs continuously in the background.
        """
        while True:
            try:
                # Wait for the next log entry
                log = await self.queue.get()
                
                session_id = log.session_id
                if session_id not in self.session_queues:
                    self.session_queues[session_id] = AsyncQueue()
                
                await self.session_queues[session_id].put(log)
                self.queue.task_done()
                
            except asyncio.CancelledError:
                # Handle cancellation gracefully
                logger.info("Distribute task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in distribute: {str(e)}")
                await asyncio.sleep(0.1)

    async def pop(self, session_id: str, poll_interval: float = 0.5, timeout: float = None):
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
                # Check if the queue is empty
                if self.queue.empty():
                    # If timeout is enabled and the timer has started, check if the timeout is reached
                    if timeout is not None \
                        and last_log_time is not None \
                        and (time.time() - last_log_time) >= (timeout if last_log_content != REASONING_STOP_TOKEN else 5 * timeout):
                        break  # Exit if the timeout since the first log is reached
                    await asyncio.sleep(poll_interval)  # Wait before checking the queue again
                    continue
                
                # Try to get an item from the queue
                log: LogEntry = await self.queue.get()
                
                if log.session_id == session_id:
                    self.queue.task_done()
                    # Start the timer after the first log is extracted
                    if last_log_time is None:
                        last_log_time = time.time()
                    last_log_content = log.message
                    yield log.message
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

    async def pop_from_session_queue(self, session_id: str):
        """
        Pop messages from a session-specific queue.
        :param session_id: Session ID to pop messages from.
        """
        if session_id not in self.session_queues:
            self.session_queues[session_id] = AsyncQueue()
            return []

        messages = []
        session_queue = self.session_queues[session_id]
        
        while not session_queue.empty():
            try:
                log = await session_queue.get_nowait()
                messages.append(log.message)
                session_queue.task_done()
            except asyncio.QueueEmpty:
                break
            
        return messages

    async def cleanup(self):
        """
        Cleanup method to ensure all queues are properly emptied.
        Should be called when shutting down the logger.
        """
        try:
            await self.queue.join()
            for session_queue in self.session_queues.values():
                await session_queue.join()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

# Global logger instance
_logger = Logger()