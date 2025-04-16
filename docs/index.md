
# AiCore Documentation

Welcome to the official documentation for **AiCore** (`core-for-ai`), a Python-based AI core system providing:

- **Multi-provider LLM integration** (OpenAI, Anthropic, Groq, Mistral, NVIDIA, etc.)
- **Embeddings system** with provider-agnostic interface
- **Configuration management** (YAML/env vars)
- **Observability** with metrics collection and visualization
- **Supporting systems** (logging, utils, retry mechanisms)

## Design Philosophy

1. **Provider-agnostic** - Switch between LLM providers with minimal code changes
2. **Async-first** - Built for high-performance AI applications
3. **Observability-ready** - Built-in metrics collection and dashboard
4. **Modular architecture** - Easily extendable components
5. **Production-ready** - Robust error handling and retry mechanisms

## Core Features

### LLM System
- Unified interface for multiple providers
- Sync/async support
- Streaming responses
- Usage tracking and cost estimation
- [Learn more](/llm/overview.md)

### Configuration
- YAML and environment variable support
- Provider-specific settings
- Model metadata integration
- [Configuration guide](/config/llmconfig.md)

### Observability
- Operation tracking
- Performance metrics
- Cost analysis
- Dashboard visualization
- [Observability overview](/observability/overview.md)

## Getting Started

1. [Installation Guide](/quickstart/installation.md)
2. [Making Your First Request](/quickstart/first-request.md)
3. [Configuration Examples](/config/llmconfig.md)

## Provider Documentation

- [OpenAI](/providers/openai.md)
- [Anthropic](/providers/anthropic.md)
- [Groq](/providers/groq.md)
- [Mistral](/providers/mistral.md)
- [NVIDIA](/providers/nvidia.md)
- [Gemini](/providers/gemini.md)
- [OpenRouter](/providers/openrouter.md)
- [DeepSeek](/providers/deepseek.md)

## Advanced Topics

- [Models Metadata System](/llm/models_metadata.md)
- [Base Provider Interface](/llm/base_provider.md)
- [Retry Mechanism](/llm/retry.md)
- [Usage Tracking](/llm/usage.md)
- [SQL Integration](/observability/sql.md)
- [Polars Integration](/observability/polars.md)

## Examples & Showcase

- [Example Projects](/examples/README.md)
- [Built with AiCore](/built-with-aicore.md)

## Support

For issues or questions, please open an issue on our [GitHub repository](https://github.com/BrunoV21/AiCore).