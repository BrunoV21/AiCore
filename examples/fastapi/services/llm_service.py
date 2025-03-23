import os
import uuid
from typing import Dict, List, Optional
from fastapi import HTTPException
import asyncio

from aicore.logger import _logger
from aicore.config import Config
from aicore.llm import Llm
from config import CONFIG_PATH
from models.schemas import LlmConfig

# LLM session storage
llm_sessions: Dict[str, Llm] = {}

async def initialize_llm_session(session_id: str, config: Optional[LlmConfig] = None) -> Llm:
    """
    Initialize or retrieve an LLM session
    
    Args:
        session_id: The session identifier
        config: Optional custom LLM configuration
        
    Returns:
        An initialized LLM instance
    """
    if session_id in llm_sessions:
        return llm_sessions[session_id]
    
    try:
        # Initialize LLM based on whether custom config is provided
        if config:
            # Convert Pydantic model to dict and use for LLM initialization
            config_dict = config.dict(exclude_none=True)
            llm = Llm.from_config(config_dict)
        else:
            # Use the default configuration from environment
            os.environ["CONFIG_PATH"] = CONFIG_PATH
            config = Config.from_yaml()
            llm = Llm.from_config(config.llm)
            
        llm_sessions[session_id] = llm
        return llm
    except Exception as e:
        print(f"Error initializing LLM for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize LLM: {str(e)}")

async def set_llm(config: LlmConfig) -> str:
    """
    Set a custom LLM configuration and return a new session ID
    
    Args:
        config: The LLM configuration to use
        
    Returns:
        A new session ID linked to the configured LLM
    """
    try:
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Initialize the LLM with the provided configuration
        await initialize_llm_session(session_id, config)
        
        return session_id
    except Exception as e:
        print(f"Error setting custom LLM: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to set custom LLM: {str(e)}")
    
def trim_messages(messages, tokenizer_fn, max_tokens :Optional[int]=None):
    max_tokens = max_tokens or int(os.environ.get("MAX_HISTORY_TOKENS", 16000))
    while messages and sum(len(tokenizer_fn(msg)) for msg in messages) > max_tokens:
        messages.pop(0)  # Remove from the beginning
    return messages
    
async def run_concurrent_tasks(llm, message):
    asyncio.create_task(llm.acomplete(message))
    asyncio.create_task(_logger.distribute())
    # Stream logger output while LLM is running
    while True:        
        async for chunk in _logger.get_session_logs(llm.session_id):
            yield chunk  # Yield each chunk directly

def simulate_llm_response(message: str) -> List[str]:
    """Simulate LLM response by breaking a dummy response into chunks."""
    response = f"This is a simulated response to: '{message}'. In a real implementation, this would be the actual output from your LLM model. The response would be generated in chunks and streamed back to the client as they become available."
    
    # Break into chunks of approximately 10 characters
    chunks = []
    for i in range(0, len(response), 10):
        chunks.append(response[i:i+10])
    
    return chunks

def cleanup_llm_sessions():
    """Clean up LLM sessions"""
    llm_sessions.clear()