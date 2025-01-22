import pytest
from unittest.mock import AsyncMock, MagicMock
from aicore.llm.providers import BaseProvider
from aicore.llm.config import LlmConfig

@pytest.fixture
def mock_config():
    return LlmConfig(
        model="gpt-4",
        temperature=0.7,
        max_tokens=150,
        provider="openai",
        api_key="test_key"
    )

@pytest.fixture
def base_provider(mock_config):
    provider = BaseProvider.from_config(mock_config)
    provider.completion_fn = MagicMock()
    provider.acompletion_fn = AsyncMock()
    return provider

def test_completion_sync(base_provider):
    prompt = "Hello, how are you?"
    mock_response = "I'm fine, thank you!"
    base_provider.completion_fn.return_value = mock_response

    result = base_provider.complete(prompt, stream=False)

    base_provider.completion_fn.assert_called_once()
    assert result == mock_response

@pytest.mark.asyncio
async def test_completion_async(base_provider):
    prompt = "Hello, how are you?"
    mock_response = "I'm fine, thank you!"
    base_provider.acompletion_fn.return_value = mock_response

    result = await base_provider.acomplete(prompt, stream=False)

    base_provider.acompletion_fn.assert_called_once()
    assert result == mock_response

def test_prepare_completion_args(base_provider):
    prompt = "Hello, world!"
    args = base_provider._prepare_completion_args(prompt)
    assert args["messages"][0]["content"][0]["text"] == prompt

def test_stream_output(base_provider):
    # Mock stream with MagicMock to simulate the expected structure
    mock_chunk_1 = MagicMock()
    mock_chunk_1.delta.content = "Hello"
    mock_chunk_2 = MagicMock()
    mock_chunk_2.delta.content = " world!"

    mock_stream = [[mock_chunk_1], [mock_chunk_2]]

    base_provider.normalize_fn = lambda chunk: chunk  # Return the mock chunk directly

    result = base_provider._stream(mock_stream)

    assert result == "Hello world!"

@pytest.mark.asyncio
async def test_astream_output(base_provider):
    # Mock stream with MagicMock to simulate the expected structure
    mock_chunk_1 = MagicMock()
    mock_chunk_1.delta.content = "Async"
    mock_chunk_2 = MagicMock()
    mock_chunk_2.delta.content = " test!"

    mock_stream = [[mock_chunk_1], [mock_chunk_2]]
    base_provider.normalize_fn = lambda chunk: chunk

    async def mock_generator():
        for chunk in mock_stream:
            yield chunk

    result = await base_provider._astream(mock_generator())
    assert result == "Async test!"
