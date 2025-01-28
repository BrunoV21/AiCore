import os
from loguru import logger
from pydantic import BaseModel, field_validator
from queue import Queue, Empty
from datetime import datetime

from aicore.const import DEFAULT_LOGS_DIR

class LogEntry(BaseModel):
    session_id :str=""
    message :str
    timestamp :str=None

    @field_validator("timestamp", mode="after")
    @classmethod
    def init_timestamp(cls, timestamp :str)->str:
        if not timestamp:
            timestamp = str(datetime.now().isoformat())
        return timestamp

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

        # Central log queue
        self.queue = Queue()
        # Session-based queues
        self.session_queues = {}

    def log_chunk_to_queue(self, message: str, session_id: str):
        """
        Log a message to the central queue and the log file.
        :param session_id: Unique session ID for the log.
        :param level: Log level (INFO, DEBUG, ERROR, etc.).
        :param message: Message to log.
        """
        log_entry = LogEntry(
            session_id=session_id,
            message=message
        )
        self.queue.put(log_entry)
        print(message, end="")
        self.distribute()

    def log_completion(self):
        """
        not implemented yet
        """
        # logger.log(level.upper(), f"[session_id={session_id}] {message}")

    async def pop(self, session_id: str, poll_interval: float = 0.5):
        """
        Asynchronously retrieves logs for a given session ID.
        Uses yield to continuously return logs as they become available.
        
        :param session_id: Unique session ID to filter logs.
        :param poll_interval: Time in seconds to wait before checking the queue again.
        """
        while True:
            found = False
            temp_queue = Queue()

            while not self.queue.empty():
                try:
                    log = self.queue.get_nowait()
                    if log.session_id == session_id:
                        yield log.message
                        found = True
                    else:
                        temp_queue.put(log)
                except Empty:
                    break

            # Restore non-matching logs to the original queue
            while not temp_queue.empty():
                self.queue.put(temp_queue.get())

    def distribute(self):
        """
        Distribute logs from the central queue to session-specific queues.
        """
        while not self.queue.empty():
            log = self.queue.get()
            session_id = log.session_id
            if session_id not in self.session_queues:
                self.session_queues[session_id] = Queue()
            self.session_queues[session_id].put(log)

    def pop_from_session_queue(self, session_id: str):

        if session_id not in self.session_queues:
            self.session_queues[session_id] = Queue()

        session_queue = self.session_queues[session_id]

        while True:
            if not session_queue.empty():
                yield session_queue.get().message
            else:
                break

    def get_all_logs_in_queue(self) -> list:
        """
        Retrieve all logs currently in the central log queue without removing them.
        :return: List of all log entries in the central queue.
        """
        logs = []
        temp_queue = Queue()

        # Transfer logs to a temporary queue to inspect them
        while not self.queue.empty():
            log = self.queue.get()
            logs.append(log)
            temp_queue.put(log)

        # Restore logs to the original queue
        while not temp_queue.empty():
            self.queue.put(temp_queue.get())

        return logs

_logger = Logger()