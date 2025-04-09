import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from aicore.llm.llm import Llm
from aicore.llm.config import LlmConfig
import json

class MockResponse:
    def __init__(self, chunks, usage=None):
        self.chunks = [chunks]
        self.usage = usage

    def __iter__(self):
        for chunks in self.chunks:
            yield chunks

    async def __aiter__(self):
        for chunks in self.chunks:
            yield chunks

class MockMistralResponse:
    def __init__(self, chunks):
        self.chunks = [(chunks)]

    def __iter__(self):
        for chunks in self.chunks:
            yield chunks

    async def __aiter__(self):
        for chunks in self.chunks:
            yield chunks
class MockChunk:
    def __init__(self, chunk_content):
        self.choices = [MockChoices(chunk_content)]
        self.usage = None
        self.x_groq = None

class MockMistralChunk:
    def __init__(self, data):
        self.data = MockData(data)

class MockData:
    def __init__(self, choices):
        self.choices = [MockChoices(choices)]       
        self.usage = None
class MockChoices:
    def __init__(self, delta):
        self.delta = MockDelta(delta)

class MockDelta:
    def __init__(self, content):
        self.content = content

class MockUsage:
    def __init__(self, total_tokens):
        self.total_tokens = total_tokens

def MockGeminiTokenizer(content):
    return [_ for _ in content.split(" ")]

@pytest.fixture
def mock_openai(*args, **kwargs):
    mock_openai = MagicMock()
    mock_openai.complete = MagicMock(return_value=MockResponse(MockChunk("mocked response")))
    mock_openai.acomplete = AsyncMock(return_value=MockResponse(MockChunk("mocked async response")))
    return mock_openai

@pytest.fixture
def mock_openai_json(*args, **kwargs):
    mock_openai = MagicMock()
    mock_openai.complete = MagicMock(return_value=MockResponse(MockChunk(json.dumps({"response": "mocked"}))))
    mock_openai.acomplete = AsyncMock(return_value=MockResponse(MockChunk(json.dumps({"response": "async mocked"}))))
    return mock_openai

@pytest.fixture
def mock_mistral(*args, **kwargs):
    mock_mistral = MagicMock()
    mock_mistral.complete = MagicMock(return_value=MockMistralResponse(MockMistralChunk("mocked response")))
    mock_mistral.acomplete = AsyncMock(return_value=MockMistralResponse(MockMistralChunk("mocked async response")))
    return mock_mistral

@pytest.fixture
def mock_mistral_json(*args, **kwargs):
    mock_mistral = MagicMock()
    mock_mistral.complete = MagicMock(return_value=MockMistralResponse(MockMistralChunk(json.dumps({"response": "mocked"}))))
    mock_mistral.acomplete = AsyncMock(return_value=MockMistralResponse(MockMistralChunk(json.dumps({"response": "async mocked"}))))
    return mock_mistral

@pytest.fixture
def mock_gemini_tokenizer(*args, **kwargs):
    mock_gemini = MagicMock()
    mock_gemini.tokenizer_fn = MagicMock(return_value=MockGeminiTokenizer("Hi there"))
    return mock_gemini

@pytest.fixture
def llm_config_openai():
    return LlmConfig(provider="openai", api_key="test_key", model="gpt-4")

@pytest.fixture
def llm_config_mistral():
    return LlmConfig(provider="mistral", api_key="test_key", model="mistral-7b")

@pytest.fixture
def llm_config_groq():
    return LlmConfig(provider="groq", api_key="test_key", model="mixtral-8x7b-32768")

@pytest.fixture
def llm_config_gemini():
    return LlmConfig(provider="gemini", api_key="test_key", model="gemini-pro")

@pytest.fixture
def llm_config_nvidia():
    return LlmConfig(provider="nvidia", api_key="test_key", model="nemotron-4")

@patch('aicore.llm.providers.base_provider.LlmBaseProvider.validate_config')
@pytest.mark.parametrize("provider_name", ["openai", "groq", "gemini", "mistral", "nvidia"])
@pytest.mark.asyncio
async def test_llm_complete(mock_validate_config, provider_name,  mock_openai, mock_mistral, llm_config_openai,
        llm_config_mistral, llm_config_groq, llm_config_gemini, llm_config_nvidia):
    
    config = {
        "openai": llm_config_openai,
        "mistral": llm_config_mistral,
        "groq": llm_config_groq,
        "gemini": llm_config_gemini,
        "nvidia": llm_config_nvidia
    }[provider_name]

    if provider_name == "mistral":
        mock_openai = mock_mistral
    
    mock_validate_config.return_value = None
    # Initialize Llm with the given configuration
    llm = Llm.from_config(config)

    llm.provider.completion_fn = mock_openai.complete
    llm.provider.acompletion_fn = mock_openai.acomplete
    
    # Call the complete method with a test prompt
    prompt = "test prompt"
    # Test with string input
    response = llm.complete(prompt)
    aresponse = await llm.acomplete(prompt)
    # Assert that the response is a string
    assert isinstance(response, str)
    # Assert that the response contains the mocked response
    assert "mocked" in response
    # Assert that the response is a string
    assert isinstance(aresponse, str)
    # Assert that the response contains the mocked response
    assert "mocked" in aresponse
    # Assert that the API was called once
    if provider_name == "openai":
        mock_openai.complete.assert_called_once()
        mock_openai.acomplete.assert_called_once()

@patch('aicore.llm.providers.base_provider.LlmBaseProvider.validate_config')
@pytest.mark.parametrize("provider_name", ["openai", "groq", "gemini", "mistral", "nvidia"])
@pytest.mark.asyncio
async def test_llm_complete_json(mock_validate_config, provider_name, mock_openai_json, mock_mistral_json, llm_config_openai,
        llm_config_mistral, llm_config_groq, llm_config_gemini, llm_config_nvidia):
    
    config = {
        "openai": llm_config_openai,
        "mistral": llm_config_mistral,
        "groq": llm_config_groq,
        "gemini": llm_config_gemini,
        "nvidia": llm_config_nvidia
    }[provider_name]

    if provider_name == "mistral":
        mock_openai_json = mock_mistral_json
    
    mock_validate_config.return_value = None
    # Initialize Llm with the given configuration
    llm = Llm.from_config(config)

    llm.provider.completion_fn = mock_openai_json.complete
    llm.provider.acompletion_fn = mock_openai_json.acomplete
    
    # Call the complete method with a test prompt
    prompt = "test prompt"
    # Test with string input
    response = llm.complete(prompt, json_output=True)
    aresponse = await llm.acomplete(prompt, json_output=True)
    # Assert that the response is a string
    assert isinstance(response, dict)
    # Assert that the response contains the mocked response
    assert "mocked" in response.values()
    # Assert that the response is a string
    assert isinstance(aresponse, dict)
    # Assert that the response contains the mocked response
    assert "async mocked" in aresponse.values()

    # Assert that the API was called once
    if provider_name == "openai":
        mock_openai_json.complete.assert_called_once()
        mock_openai_json.acomplete.assert_called_once()

@patch('aicore.llm.providers.base_provider.LlmBaseProvider.validate_config')
@pytest.mark.parametrize("provider_name", ["openai", "mistral", "gemini", "groq", "nvidia"])
@pytest.mark.asyncio
async def test_llm_tokenizer(mock_validate_config, provider_name, llm_config_openai, llm_config_mistral, llm_config_groq, llm_config_gemini, llm_config_nvidia, mock_gemini_tokenizer):
    config = {
        "openai": llm_config_openai,
        "mistral": llm_config_mistral,
        "groq": llm_config_groq,
        "gemini": llm_config_gemini,
        "nvidia": llm_config_nvidia
    }[provider_name]    
    
    mock_validate_config.return_value = None
    llm = Llm.from_config(config)

    if provider_name == "gemini":
        llm.provider.tokenizer_fn = mock_gemini_tokenizer.tokenizer_fn
    
    prompt = "test prompt"
    
    # Call the tokenizer function
    tokens = llm.tokenizer(prompt)
    
    # Assert that the tokenizer returns a list
    assert isinstance(tokens, list)
    # Assert that the list of tokens is not empty
    assert len(tokens) > 0