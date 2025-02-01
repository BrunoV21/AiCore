import pytest
import asyncio
from datetime import datetime
from time import time
from typing import AsyncGenerator

# Import the classes from your module
from aicore.logger import Logger, LogEntry

@pytest.fixture
def logger():
    """Fixture to create and cleanup a logger instance for each test."""
    test_logs_dir = "test_logs"
    logger_instance = Logger(logs_dir=test_logs_dir)
    return logger_instance

@pytest.mark.asyncio
async def test_log_chunk_to_queue(logger):
    """Test basic logging functionality with timeout."""
    session_id = "test_session"
    test_message = "Test message"
    
    await logger.log_chunk_to_queue(test_message, session_id)
    
    # Get logs with timeout
    async def get_logs():
        return logger.get_all_logs_in_queue()
    
    logs = await asyncio.wait_for(asyncio.create_task(get_logs()), timeout=2.0)
    
    assert len(logs) == 1
    assert logs[0].message == test_message
    assert logs[0].session_id == session_id
    assert isinstance(logs[0].timestamp, str)

@pytest.mark.asyncio
async def test_pop_with_timeout(logger):
    """Test pop functionality with timeout."""
    session_id = "test_session"
    test_messages = ["Message 1", "Message 2", "Message 3"]
    
    # Log multiple messages
    for msg in test_messages:
        await logger.log_chunk_to_queue(msg, session_id)
    
    received_messages = []
    
    # Create async generator for pop method
    async def collect_messages():
        async for message in logger.pop(session_id):
            received_messages.append(message)
            if len(received_messages) == len(test_messages):
                break
    
    # Run with timeout
    try:
        await asyncio.wait_for(collect_messages(), timeout=2.0)
    except asyncio.TimeoutError:
        pytest.fail("Pop operation timed out")
    
    assert received_messages == test_messages

@pytest.mark.asyncio
async def test_multiple_sessions(logger):
    """Test handling of multiple sessions with timeout."""
    session_1 = "session_1"
    session_2 = "session_2"
    
    # Log messages for different sessions
    await logger.log_chunk_to_queue("Message 1 for session 1", session_1)
    await logger.log_chunk_to_queue("Message 1 for session 2", session_2)
    await logger.log_chunk_to_queue("Message 2 for session 1", session_1)
    
    # Test session queues are created
    assert set(logger.all_sessions_in_queue) == {session_1, session_2}

@pytest.mark.asyncio
async def test_reasoning_stop_token(logger):
    """Test that pop stops when encountering REASONING_STOP_TOKEN."""
    from aicore.logger import REASONING_STOP_TOKEN
    
    session_id = "test_session"
    messages = [
        "Message 1",
        f"Message 2 {REASONING_STOP_TOKEN}",
        "Message 3"  # This shouldn't be received
    ]
    
    for msg in messages:
        await logger.log_chunk_to_queue(msg, session_id)
    
    received_messages = []
    async for message in logger.pop(session_id):
        received_messages.append(message)
    
    assert len(received_messages) == 2
    assert REASONING_STOP_TOKEN in received_messages[1]
    assert messages[2] not in received_messages