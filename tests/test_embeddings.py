import pytest
from unittest.mock import MagicMock
from aicore.embeddings.embeddings import Embeddings, Providers
from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings.providers.base_provider import EmbeddingsBaseProvider
from typing import List

# Fixture to create a mock EmbeddingsConfig for testing.
# This allows us to easily configure the provider, api_key, and model for different test cases.
@pytest.fixture
def mock_embeddings_config():
    return EmbeddingsConfig(
        provider="openai",
        api_key="test_api_key",
        model="test_model"
    )

# Fixture to create a mock EmbeddingsBaseProvider for testing.
# This allows us to isolate the Embeddings class from the actual provider implementation.
# The vector_dimensions attribute is set to a default value of 1536.
@pytest.fixture
def mock_base_provider():
    mock = MagicMock(spec=EmbeddingsBaseProvider)
    mock.vector_dimensions = 1536
    return mock

# Test case to verify the correct initialization of the Embeddings class.
# It checks if the provider is correctly set and if the vector dimensions are correctly retrieved.
# The test uses monkeypatch to mock the from_config method of the provider.
def test_embeddings_initialization(mock_embeddings_config, mock_base_provider, monkeypatch):
    monkeypatch.setattr(Providers.OPENAI.value, "from_config", MagicMock(return_value=mock_base_provider))
    embeddings = Embeddings.from_config(mock_embeddings_config)
    assert embeddings.provider == mock_base_provider
    assert embeddings.vector_dimensions == 1536
    Providers.OPENAI.value.from_config.assert_called_once_with(mock_embeddings_config)

# Test case to verify the generate method of the Embeddings class.
# It checks if the generate method of the provider is called correctly and if the result is as expected.
# The test uses monkeypatch to mock the from_config method of the provider.
def test_embeddings_generate(mock_embeddings_config, mock_base_provider, monkeypatch):
    monkeypatch.setattr(Providers.OPENAI.value, "from_config", MagicMock(return_value=mock_base_provider))
    embeddings = Embeddings.from_config(mock_embeddings_config)
    text_batches = ["text1", "text2"]
    mock_base_provider.generate.return_value = ["vector1", "vector2"]
    result = embeddings.generate(text_batches)
    assert result == ["vector1", "vector2"]
    mock_base_provider.generate.assert_called_once_with(text_batches)

# Test case to verify the agenerate method of the Embeddings class.
# It checks if the agenerate method of the provider is called correctly and if the result is as expected.
# The test uses monkeypatch to mock the from_config method of the provider.
@pytest.mark.asyncio
async def test_embeddings_agenerate(mock_embeddings_config, mock_base_provider, monkeypatch):
    monkeypatch.setattr(Providers.OPENAI.value, "from_config", MagicMock(return_value=mock_base_provider))
    embeddings = Embeddings.from_config(mock_embeddings_config)
    text_batches = ["text1", "text2"]
    mock_base_provider.agenerate.return_value = ["vector1", "vector2"]
    result = await embeddings.agenerate(text_batches)
    assert result == ["vector1", "vector2"]
    mock_base_provider.agenerate.assert_called_once_with(text_batches)

# Test case to verify the provider setter of the Embeddings class.
# It checks if the provider can be set to a new provider and if the vector dimensions are updated accordingly.
# The test uses monkeypatch to mock the from_config method of the provider.
def test_embeddings_provider_setter(mock_embeddings_config, mock_base_provider, monkeypatch):
    monkeypatch.setattr(Providers.OPENAI.value, "from_config", MagicMock(return_value=mock_base_provider))
    embeddings = Embeddings.from_config(mock_embeddings_config)
    new_mock_provider = MagicMock(spec=EmbeddingsBaseProvider)
    new_mock_provider.vector_dimensions = 2048
    embeddings.provider = new_mock_provider
    assert embeddings.provider == new_mock_provider
    assert embeddings.vector_dimensions == 2048

# Test case to verify the from_config class method of the Embeddings class.
# It checks if the config is correctly set when creating an Embeddings instance from a config.
def test_embeddings_from_config(mock_embeddings_config):
    embeddings = Embeddings.from_config(mock_embeddings_config)
    assert embeddings.config == mock_embeddings_config