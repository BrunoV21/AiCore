
# OpenRouter Provider

The OpenRouter provider enables access to multiple LLM models through the OpenRouter API, providing a unified interface to various AI models from different providers.

## Key Features

- **Multi-model access**: Single API endpoint for multiple LLM providers
- **Cost transparency**: Clear pricing information for all supported models
- **Standardized API**: Consistent interface across different model providers
- **Usage tracking**: Built-in token counting and cost calculation
- **Model switching**: Easily switch between different models without changing providers

## Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="openrouter",
    api_key="your_openrouter_api_key",  # Get from https://openrouter.ai/keys
    model="openai/gpt-4",  # Format: provider/model-name
    temperature=0.7,
    max_tokens=1000
)
```

## Supported Models

OpenRouter supports models from multiple providers including:

| Provider | Example Models |
|----------|----------------|
| OpenAI | `openai/gpt-3.5-turbo`, `openai/gpt-4`, `openai/gpt-4-turbo` |
| Anthropic | `anthropic/claude-2`, `anthropic/claude-3-opus` |
| Google | `google/gemini-pro` |
| Mistral | `mistralai/mistral-tiny`, `mistralai/mistral-medium` |
| Meta | `meta-llama/llama-2-13b-chat` |

For a complete list of available models, see the [OpenRouter Models page](https://openrouter.ai/models).

## Pricing

Pricing varies by model and is calculated per token. You can check model pricing programmatically:

```python
from aicore.models_metadata import METADATA

model_data = METADATA["openrouter-openai/gpt-4"]
print(f"Price per 1k tokens: ${model_data.pricing.completion/10:.4f}")
```

## Usage Examples

### Basic Completion

```python
from aicore.llm import Llm

llm = Llm(config=config)
response = llm.complete("Explain quantum computing in simple terms")
print(response.content)
```

### Streaming Response

```python
async for chunk in llm.stream("Write a poem about AI"):
    print(chunk, end="", flush=True)
```

### With Message History

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "What's the weather today?"}
]

response = llm.chat(messages)
```

## Advanced Features

### Custom Headers

OpenRouter supports additional headers for features like user tracking:

```python
config = LlmConfig(
    provider="openrouter",
    api_key="your_api_key",
    model="anthropic/claude-3-opus",
    headers={
        "HTTP-Referer": "https://yourdomain.com",
        "X-Title": "Your App Name"
    }
)
```

### Fallback Models

```python
config = LlmConfig(
    provider="openrouter",
    api_key="your_api_key",
    model="anthropic/claude-3-opus",
    fallbacks=["openai/gpt-4", "google/gemini-pro"]
)
```

## Observability Integration

All OpenRouter operations are automatically tracked by the observability system:

```python
from aicore.observability.collector import LlmOperationCollector

# View OpenRouter operations
operations = LlmOperationCollector.polars_from_db(provider="openrouter")
print(operations.select(["model", "latency_ms", "total_tokens"]))
```

## Troubleshooting

- **Authentication Errors**: Verify your API key at [OpenRouter Keys](https://openrouter.ai/keys)
- **Model Not Found**: Check the exact model name format (provider/model-name)
- **Rate Limits**: OpenRouter has default rate limits - consider upgrading if needed