
# Configuration Guide

Welcome to the AiCore Configuration documentation! This section covers all aspects of configuring the AiCore system.

## Configuration Options

1. [LLM Configuration](./llmconfig.md) - Configure LLM providers and models
2. [Environment Variables](./env-example.md) - Reference for environment-based configuration
3. [YAML Configuration](../config/) - Example configuration files

## Key Concepts

- YAML and environment variable support
- Pydantic validation for all configurations
- Provider-specific configuration options
- Hierarchical configuration (global → provider → model)
- Environment variable overrides

## Configuration Sources

AiCore supports multiple configuration sources with the following precedence:
1. Environment variables (highest priority)
2. YAML configuration files
3. Default values (lowest priority)

## Getting Started

1. Copy the example configuration from `config/config_example_*.yml`
2. Modify the settings for your provider
3. Set any sensitive values via environment variables
4. Initialize your components using the configuration

For detailed provider-specific configuration, see the [Providers section](../providers/).

## Environment Variables Reference

The following environment variables are commonly used:

```bash
# Core Configuration
AICORE_LOG_LEVEL=INFO
AICORE_CACHE_ENABLED=true

# LLM Providers
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
GROQ_API_KEY=your-key-here

# Database Connections
CONNECTION_STRING="postgresql://user:password@localhost/dbname"
ASYNC_CONNECTION_STRING="postgresql+asyncpg://user:password@localhost/dbname"

# Custom Models
CUSTOM_MODELS='["gemini-2.5-pro-exp-03-25"]'
```

See the complete [.env-example](./env-example.md) file for all available options.