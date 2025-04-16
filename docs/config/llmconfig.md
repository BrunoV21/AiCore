
# LLM Configuration Guide

## Overview
The `LlmConfig` class provides a unified configuration interface for all supported LLM providers in the AiCore system. It supports both YAML and Python-based configuration with environment variable overrides.

## Core Configuration Options

### Required Parameters
- `provider`: Supported LLM provider (e.g., `openai`, `anthropic`, `groq`, `mistral`)
- `api_key`: Provider API key (can be set via environment variable)
- `model`: Model identifier (e.g., `gpt-4`, `claude-3-sonnet`)

### Optional Parameters
- `base_url`: Custom API endpoint URL
- `temperature`: Sampling temperature (0.0-1.0)
- `max_tokens`: Maximum tokens to generate (default: model-specific)
- `timeout`: Request timeout in seconds
- `stream`: Enable streaming responses (default: True)
- `cache`: Enable response caching (default: False)
- `thinking`: Enable step-by-step reasoning (Anthropic models)

## Configuration Methods

### YAML Configuration
```yaml
# config.yml example
provider: openai
api_key: ${OPENAI_API_KEY}
model: gpt-4
temperature: 0.7
max_tokens: 1000
```

### Python Configuration
```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="anthropic",
    api_key="your_api_key",
    model="claude-3-sonnet",
    temperature=0.5,
    max_tokens=2000
)
```

### Environment Variables
All parameters can be set via environment variables:
```bash
export LLM_PROVIDER=openai
export LLM_API_KEY=sk-...
export LLM_MODEL=gpt-4
export LLM_TEMPERATURE=0.7
```

## Advanced Features

### Nested Configurations
```yaml
# With reasoner configuration
provider: anthropic
api_key: sk-ant-...
model: claude-3-opus
reasoner:
  provider: groq
  api_key: gsk-...
  model: llama3-70b
  temperature: 0.3
```

### Model Metadata Integration
The configuration system automatically applies model-specific defaults from `models_metadata.json`:
- Context window size
- Maximum tokens
- Default pricing

## Validation
The configuration system performs validation on:
- Provider/model compatibility
- Temperature range (0.0-1.0)
- Maximum token limits
- Required API keys

## Best Practices
1. **Secure Storage**: Always store API keys in environment variables or secret managers
2. **Model Selection**: Choose models based on task requirements and cost considerations
3. **Testing Configs**: Validate configurations in a non-production environment first
4. **Version Control**: Exclude sensitive values from version control using `.gitignore`

## See Also
- [Models Metadata Documentation](../llm/models_metadata.md)
- [Base Provider Interface](../llm/base_provider.md)
- [Usage Tracking](../llm/usage.md)