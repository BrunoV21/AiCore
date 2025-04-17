
# LLM System

The LLM System provides a unified interface for interacting with various language model providers through a standardized API. This modular system supports multiple providers while maintaining consistent behavior across implementations.

## Core Components

1. [Base Provider Interface](./base_provider.md) - Abstract base class for all LLM providers
2. [Model Metadata](./models_metadata.md) - Information about supported models
3. [Usage Tracking](./usage.md) - Cost and token tracking
4. [Retry Mechanism](./retry.md) - Automatic retry and fallback logic

## Key Features

- **Multi-provider Support**: Single interface for OpenAI, Anthropic, Gemini and more
- **Operation Modes**: Both synchronous and asynchronous operations
- **Advanced Capabilities**:
  - Streaming responses
  - Reasoning augmentation
  - Template-based prompting
- **Observability**: Built-in usage tracking and monitoring

## Getting Started

```python
from aicore.llm import Llm
from aicore.config import load_config

# Load configuration
config = load_config("config.yml")

# Initialize LLM client
llm = Llm.from_config(config)

# Make completion request
response = llm.complete("Hello, how are you?")
```

## Next Steps

- Explore [Provider Implementations](../providers/) for specific provider details
- Learn about [Configuration Options](../config/llmconfig.md) for fine-tuning behavior
- Check [Examples](../examples/) for practical implementation patterns