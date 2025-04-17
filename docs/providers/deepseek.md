
# DeepSeek Provider

DeepSeek provider implementation for the AiCore LLM system.

## Features

- Supports DeepSeek's chat and reasoning models
- Implements token counting and cost tracking
- Includes happy hour pricing support
- Compatible with OpenAI API format
- Full observability integration (metrics, logging, tracing)

## Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="deepseek",
    api_key="your_api_key",  # Get from DeepSeek console
    model="deepseek-chat",  # or "deepseek-reasoner"
    base_url="https://api.deepseek.com/v1",  # Optional custom endpoint
    timeout=30,  # Request timeout in seconds
    max_retries=3  # Automatic retry attempts
)
```

## Supported Models

| Model Name          | Description                          | Context Window |
|---------------------|--------------------------------------|----------------|
| `deepseek-chat`     | General purpose chat model           | 128K tokens    |
| `deepseek-reasoner` | Specialized reasoning model          | 128K tokens    |

## Usage Example

```python
from aicore.llm import Llm

# Initialize with config
llm = Llm(config=config)

# Basic completion
response = llm.complete("Explain quantum computing in simple terms")

# Streaming response
async for chunk in llm.stream("Write a poem about AI"):
    print(chunk, end="")

# With observability tracking
with llm.trace("user123", "analysis_task"):
    response = llm.complete("Analyze this dataset...")
```

## Advanced Features

### Custom Templates

```python
from aicore.llm.templates import SystemMessage

template = SystemMessage(
    "You are a helpful AI assistant specialized in scientific topics."
)
response = llm.complete("Explain photosynthesis", system_template=template)
```

### Observability Integration

All DeepSeek operations automatically track:
- Token usage (input/output)
- Latency metrics
- Cost calculations
- Success/failure rates

Access metrics through the [Observability Dashboard](../observability/dashboard.md).

## Pricing

DeepSeek uses token-based pricing. Current rates can be accessed programmatically:

```python
from aicore.models_metadata import METADATA

model_data = METADATA["deepseek-deepseek-chat"]
print(f"Input: ${model_data.pricing.input_per_token:.8f}/token")
print(f"Output: ${model_data.pricing.output_per_token:.8f}/token")
```

## Error Handling

The provider implements automatic retries for:
- Rate limits (429 errors)
- Server errors (5xx)
- Temporary network issues

Customize retry behavior in the `LlmConfig`.

## See Also

- [LLM Provider Basics](../llm/base_provider.md)
- [Configuration Guide](../config/llmconfig.md)
- [Observability Overview](../observability/overview.md)