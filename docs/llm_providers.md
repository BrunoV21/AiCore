
# LLM Providers Documentation

This document provides an overview of the LLM (Large Language Model) providers supported by our system, their configuration, and usage.

## Supported Providers

### 1. Gemini

**Class**: `GeminiLlm`

**Base URL**: `https://generativelanguage.googleapis.com/v1beta/openai/`

**Features**:
- Token counting using the `gemini_count_tokens` method.
- Supports both synchronous and asynchronous operations.

**Usage**:
```python
from aicore.llm.providers.gemini import GeminiLlm
from aicore.llm.config import LlmConfig

config = LlmConfig(provider="gemini", api_key="your_api_key", model="your_model")
gemini_llm = GeminiLlm.from_config(config)
```

### 2. Groq

**Class**: `GroqLlm`

**Features**:
- Supports both synchronous and asynchronous operations.
- Uses `Groq` and `AsyncGroq` clients for interactions.

**Usage**:
```python
from aicore.llm.providers.groq import GroqLlm
from aicore.llm.config import LlmConfig

config = LlmConfig(provider="groq", api_key="your_api_key", model="your_model")
groq_llm = GroqLlm.from_config(config)
```

### 3. Mistral

**Class**: `MistralLlm`

**Features**:
- Supports streaming by default.
- Uses `Mistral` client for interactions.

**Usage**:
```python
from aicore.llm.providers.mistral import MistralLlm
from aicore.llm.config import LlmConfig

config = LlmConfig(provider="mistral", api_key="your_api_key", model="your_model")
mistral_llm = MistralLlm.from_config(config)
```

### 4. Nvidia

**Class**: `NvidiaLlm`

**Base URL**: `https://integrate.api.nvidia.com/v1`

**Features**:
- Limited to 4K max output tokens.
- Does not support image uploads via OpenAI compatible requests.

**Usage**:
```python
from aicore.llm.providers.nvidia import NvidiaLlm
from aicore.llm.config import LlmConfig

config = LlmConfig(provider="nvidia", api_key="your_api_key", model="your_model")
nvidia_llm = NvidiaLlm.from_config(config)
```

### 5. OpenRouter

**Class**: `OpenRouterLlm`

**Base URL**: `https://openrouter.ai/api/v1`

**Features**:
- Most Nvidia hosted models are limited to 4K max output tokens.

**Usage**:
```python
from aicore.llm.providers.openrouter import OpenRouterLlm
from aicore.llm.config import LlmConfig

config = LlmConfig(provider="openrouter", api_key="your_api_key", model="your_model")
openrouter_llm = OpenRouterLlm.from_config(config)
```

### 6. OpenAI

**Class**: `OpenAiLlm`

**Features**:
- Supports both synchronous and asynchronous operations.
- Uses `OpenAI` and `AsyncOpenAI` clients for interactions.

**Usage**:
```python
from aicore.llm.providers.openai import OpenAiLlm
from aicore.llm.config import LlmConfig

config = LlmConfig(provider="openai", api_key="your_api_key", model="your_model")
openai_llm = OpenAiLlm.from_config(config)
```

## Configuration

All providers are configured using the `LlmConfig` class. The configuration includes:
- `provider`: The name of the provider (e.g., "gemini", "groq", "mistral", "nvidia", "openai", "openrouter").
- `api_key`: The API key for authentication.
- `model`: The model to use (optional).
- `base_url`: The base URL for the API (optional).
- `temperature`: The temperature for the model (default is 0).
- `max_tokens`: The maximum number of tokens (default is 12000).
- `reasoner`: An optional reasoner configuration.

**Example Configuration**:
```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="openai",
    api_key="your_api_key",
    model="your_model",
    base_url="https://api.openai.com/v1",
    temperature=0.7,
    max_tokens=2000
)
```

## Utility Functions

### Image to Base64

**Function**: `image_to_base64`

**Description**: Encodes an image to a base64 string.

**Usage**:
```python
from aicore.llm.utils import image_to_base64

base64_image = image_to_base64("path/to/image.jpg")
```

### Parse Content

**Function**: `parse_content`

**Description**: Parses content to extract the main body, ignoring starting and ending patterns.

**Usage**:
```python
from aicore.llm.utils import parse_content

content = parse_content("```python\nprint('Hello, World!')\n```")
```

## Base Provider

All providers inherit from the `LlmBaseProvider` class, which provides common functionality such as:
- Client and asynchronous client management.
- Completion arguments and functions.
- Normalization and tokenization functions.
- Streaming support.

**Example**:
```python
from aicore.llm.providers.base_provider import LlmBaseProvider

class CustomLlm(LlmBaseProvider):
    # Implement custom provider-specific methods here
    pass
```

## Integration

The `Providers` enum in `aicore.llm.llm` provides a centralized way to instantiate providers based on their configuration.

**Example**:
```python
from aicore.llm.llm import Providers
from aicore.llm.config import LlmConfig

config = LlmConfig(provider="openai", api_key="your_api_key", model="your_model")
provider_instance = Providers.OPENAI.get_instance(config)
```

This documentation should help you understand and integrate the various LLM providers supported by our system.