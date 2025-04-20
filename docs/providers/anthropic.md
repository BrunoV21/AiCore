
# Anthropic Provider

The Anthropic provider implements support for Claude models through the Anthropic API, including Claude 3 Sonnet, Opus, and Haiku models.

## Supported Models

```python
from aicore.models_metadata import METADATA

# List available Anthropic models
anthropic_models = [model for model in METADATA if model.startswith("anthropic-")]
print(anthropic_models)
```

## Key Features

- Automatic token counting and cost tracking
- Extended thinking mode for complex reasoning
- Prompt caching control
- Async-first implementation

## Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="anthropic",
    api_key="your_api_key",
    model="claude-3-7-sonnet",
    temperature=0.7,
    max_tokens=4000,
    thinking=True  # Enable extended reasoning
)
```

## Basic Usage

```python
from aicore.llm import Llm

# Initialize LLM with Anthropic config
llm = Llm(config=config)

# Simple completion
response = llm.complete("Explain quantum computing in simple terms")
print(response)
```

## Advanced Usage

### Thinking Mode

```python
# Enable thinking mode for step-by-step reasoning
thinking_config = LlmConfig(
    provider="anthropic",
    api_key="your_api_key",
    model="claude-3-7-sonnet",
    thinking=True
)

llm = Llm(config=thinking_config)
response = llm.complete("Solve this math problem: (3x + 5 = 20)")
```

## Model Specifications

| Model Name | Context Window | Best For |
|------------|----------------|----------|
| claude-3-7-sonnet | 200K tokens | Complex reasoning tasks|
| claude-3-5-haiku | 200K tokens | Fast, cost-effective |

## Additional Notes

- Requires Anthropic API key
- Supports both synchronous and asynchronous operations
- Implements automatic retries for rate limits
- Detailed usage metrics available through observability system

For advanced configuration options, see the [base provider documentation](../llm/base_provider.md).