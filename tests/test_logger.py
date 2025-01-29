import pytest
import os
from datetime import datetime
from queue import Queue
import asyncio
from unittest.mock import patch, Mock

from aicore.logger import Logger, LogEntry

@pytest.fixture
def temp_dir(tmp_path):
    """Fixture to provide a temporary directory for logs"""
    return str(tmp_path)

@pytest.fixture
def logger(temp_dir):
    """Fixture to provide a logger instance with a temporary directory"""
    return Logger(logs_dir=temp_dir)

def test_logger_initialization(temp_dir):
    """Test logger initialization and directory creation"""
    logger = Logger(logs_dir=temp_dir)
    assert os.path.exists(temp_dir)
    assert isinstance(logger.queue, Queue)
    assert isinstance(logger.session_queues, dict)

def test_log_entry_model():
    """Test LogEntry model initialization and timestamp validation"""
    # Test with provided timestamp
    timestamp = datetime.now().isoformat()
    entry = LogEntry(session_id="test123", message="Test message", timestamp=timestamp)
    assert entry.session_id == "test123"
    assert entry.message == "Test message"
    assert entry.timestamp == timestamp

    # Test with auto-generated timestamp
    entry = LogEntry(session_id="test123", message="Test message")
    print(entry.model_dump_json(indent=4))
    assert entry.timestamp is not None
    # Verify it's a valid timestamp
    datetime.fromisoformat(entry.timestamp)

def test_log_chunk_to_queue(logger):
    """Test logging chunks to the central queue"""
    session_id = "test_session"
    message = "Test message"
    
    with patch('builtins.print') as mock_print:
        logger.log_chunk_to_queue(message, session_id)
        
        # Verify message was printed
        mock_print.assert_called_once_with(message, end="")
        
        # Verify message was added to queue
        logs = logger.get_all_logs_in_queue()
        assert len(logs) == 1
        assert logs[0].session_id == session_id
        assert logs[0].message == message

def test_distribute_logs(logger):
    """Test distribution of logs to session-specific queues"""
    session_id = "test_session"
    messages = ["Message 1", "Message 2"]
    
    for msg in messages:
        logger.log_chunk_to_queue(msg, session_id)
    
    logger.distribute()
    
    # Verify messages in session queue
    assert session_id in logger.session_queues
    received_messages = logger.pop_from_session_queue(session_id)
    assert received_messages == messages

@pytest.mark.asyncio
async def test_pop_async(logger):
    """Test asynchronous log retrieval"""
    session_id = "test_session"
    messages = ["Message 1", "Message 2"]
    
    # Add messages to queue
    for msg in messages:
        logger.log_chunk_to_queue(msg, session_id)
    
    # Collect messages using pop
    received_messages = []
    async for msg in logger.pop(session_id, poll_interval=0.1):
        received_messages.append(msg)
        if len(received_messages) == len(messages):
            break
    
    assert received_messages == messages

def test_get_all_logs_in_queue(logger):
    """Test retrieving all logs without removing them from queue"""
    session_id = "test_session"
    messages = ["Message 1", "Message 2", "Message 3"]
    
    # Add messages to queue
    for msg in messages:
        logger.log_chunk_to_queue(msg, session_id)
    
    # Get all logs
    logs = logger.get_all_logs_in_queue()
    assert len(logs) == len(messages)
    
    # Verify log contents
    for i, log in enumerate(logs):
        assert log.session_id == session_id
        assert log.message == messages[i]

def test_pop_from_empty_session_queue(logger):
    """Test popping from an empty or non-existent session queue"""
    session_id = "nonexistent_session"
    
    # Should return empty list for non-existent session
    messages = logger.pop_from_session_queue(session_id)
    assert isinstance(messages, list)
    assert len(messages) == 0
    assert session_id in logger.session_queues

def test_multiple_sessions(logger):
    """Test handling multiple sessions simultaneously"""
    sessions = {
        "session1": ["Message 1-1", "Message 1-2"],
        "session2": ["Message 2-1", "Message 2-2"]
    }
    
    # Log messages for different sessions
    for session_id, messages in sessions.items():
        for msg in messages:
            logger.log_chunk_to_queue(msg, session_id)
    
    logger.distribute()
    
    # Verify each session's messages
    for session_id, expected_messages in sessions.items():
        received_messages = logger.pop_from_session_queue(session_id)
        assert received_messages == expected_messages