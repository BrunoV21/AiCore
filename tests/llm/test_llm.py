import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aicore.llm.config import LlmConfig
from aicore.llm.providers import LlmBaseProvider
from aicore.llm.llm import Llm, Providers

@pytest.fixture
def mock_config():
    return LlmConfig(
        model="gpt-4o",
        temperature=0.7,
        max_tokens=150,
        provider="openai",
        api_key="test_key"
    )

@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=LlmBaseProvider)
    provider.complete = MagicMock(return_value="Hello from mock!")
    provider.acomplete = AsyncMock(return_value="Hello from mock async!")
    return provider

def test_complete_sync(mock_config, mock_provider):
    # Patch the Providers enum's get_instance method to return our mock provider
    with patch.object(Providers, 'get_instance', return_value=mock_provider):
        llm = Llm.from_config(mock_config)
        result = llm.complete("Test prompt")
        mock_provider.complete.assert_called_once()
        assert result == "Hello from mock!"

@pytest.mark.asyncio
async def test_complete_async(mock_config, mock_provider):
    # Patch the Providers enum's get_instance method to return our mock provider
    with patch.object(Providers, 'get_instance', return_value=mock_provider):
        llm = Llm.from_config(mock_config)
        result = await llm.acomplete("Test prompt")
        mock_provider.acomplete.assert_called_once()
        assert result == "Hello from mock async!"

# Optional: Add a test to verify the provider initialization itself
def test_provider_initialization(mock_config):
    with patch.object(Providers, 'get_instance') as mock_get_instance:
        Llm.from_config(mock_config)
        mock_get_instance.assert_called_once_with(mock_config)