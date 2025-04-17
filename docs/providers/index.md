
# Provider System

The Provider System enables seamless integration with multiple LLM and embedding providers through a standardized interface, allowing easy switching between different AI services.

## Supported Providers

AiCore currently supports the following providers:

1. [OpenAI](./openai.md) - GPT models and embeddings
2. [Anthropic](./anthropic.md) - Claude models
3. [Gemini](./gemini.md) - Google's Gemini models
4. [Groq](./groq.md) - Ultra-fast inference
5. [Mistral](./mistral.md) - Open-weight models
6. [NVIDIA](./nvidia.md) - NVIDIA AI Foundation models
7. [OpenRouter](./openrouter.md) - Unified API for multiple providers

## Key Features

- **Standardized Interface**: Consistent API across all providers
- **Automatic Retry**: Built-in error handling and retry mechanisms
- **Dynamic Pricing**: Real-time cost calculation per request
- **Async Support**: Native asynchronous operations
- **Configuration Flexibility**: Provider-specific settings through YAML

## Getting Started

To use a provider:
1. Configure your provider in the config file
2. Import the desired provider class
3. Initialize with your configuration
4. Make requests through the standardized interface

For detailed instructions on each provider, select from the list above.