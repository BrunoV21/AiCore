
# OpenAI Provider

The OpenAI provider implements support for OpenAI's models including GPT-4, GPT-4-turbo, GPT-3.5-turbo, and other variants through the OpenAI API.

## Supported Models

```python
from aicore.models_metadata import METADATA

# List all supported OpenAI models
openai_models = [model for model in METADATA if model.startswith("openai-")]
print(openai_models)
```

## Key Features

- Supports all OpenAI chat and completion models
- Full streaming support with real-time token counting
- Automatic retry handling for rate limits
- Multimodal support (images via base64 encoding)
- Detailed usage tracking and cost calculation

## Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="openai",
    api_key="your_api_key",  # or set OPENAI_API_KEY environment variable
    model="gpt-4o",
    temperature=0.7,
    max_tokens=4000
)
```

## Basic Usage

```python
from aicore.llm import Llm

# Initialize with config
llm = Llm(config=config)

# Simple completion
response = llm.complete("Hello world")
print(response)
```

## Advanced Usage

### Multimodal Input

```python
import base64

# Encode image
with open("image.png", "rb") as image_file:
    base64_image = base64.b64encode(image_file.read()).decode('utf-8')

response = llm.complete(
    [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": f"data:image/png;base64,{base64_image}"}
    ]
)
```

## Error Handling

The provider automatically handles:
- Rate limits (with exponential backoff)
- API key errors
- Model availability issues
- Context window overflows

## Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Model Pricing](../llm/usage.md)
- [Base Provider Documentation](../llm/base_provider.md)