from pydantic import BaseModel, model_validator
from typing import Optional, List, Self
from queue import Queue, Empty
from datetime import datetime
from loguru import logger
import os

class LogEntry(BaseModel):
    session_id: str = ""
    message: str
    timestamp: Optional[str] = None

    @model_validator( mode="after")
    def init_timestamp(self) -> Self:
        """Initialize timestamp if not provided"""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        return self

class Logger:
    def __init__(self, logs_dir="logs"):
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

        # Central log queue
        self.queue = Queue()
        # Session-based queues
        self.session_queues = {}
        self._temp_storage = []  # Added for preserving logs during get_all_logs_in_queue

    @property
    def all_sessions_in_queue(self)->List[str]:
        return list(self.session_queues.keys())

    def log_chunk_to_queue(self, message: str, session_id: str):
        """
        Log a message to the central queue and the log file.
        :param message: Message to log.
        :param session_id: Unique session ID for the log.
        """
        log_entry = LogEntry(
            session_id=session_id,
            message=message
        )
        self.queue.put(log_entry)
        self._temp_storage.append(log_entry)  # Store for retrieval
        print(message, end="")
        # self.distribute()

    def get_all_logs_in_queue(self) -> list:
        """
        Retrieve all logs currently in the central log queue without removing them.
        :return: List of all log entries in the central queue.
        """
        return self._temp_storage.copy()  # Return copy of stored logs

    def distribute(self):
        """
        Distribute logs from the central queue to session-specific queues.
        """
        while not self.queue.empty():
            try:
                log = self.queue.get_nowait()
                session_id = log.session_id
                if session_id not in self.session_queues:
                    self.session_queues[session_id] = Queue()
                self.session_queues[session_id].put(log)
            except Empty:
                break

    async def pop(self, session_id: str, poll_interval: float = 0.5):
        """
        Asynchronously retrieves logs for a given session ID.
        :param session_id: Unique session ID to filter logs.
        :param poll_interval: Time in seconds to wait before checking the queue again.
        """
        temp_storage = []
        while True:
            while not self.queue.empty():
                try:
                    log = self.queue.get_nowait()
                    if log.session_id == session_id:
                        yield log.message
                    else:
                        temp_storage.append(log)
                except Empty:
                    break
            
            # Restore non-matching logs
            for log in temp_storage:
                self.queue.put(log)
            temp_storage.clear()

    def pop_from_session_queue(self, session_id: str):
        """
        Pop messages from a session-specific queue.
        :param session_id: Session ID to pop messages from.
        """
        if session_id not in self.session_queues:
            self.session_queues[session_id] = Queue()
            return []

        messages = []
        while not self.session_queues[session_id].empty():
            try:
                log = self.session_queues[session_id].get_nowait()
                messages.append(log.message)
            except Empty:
                break
        return messages
    
_logger = Logger()