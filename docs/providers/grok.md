
# Grok Provider

The Grok provider implements support for xAI's Grok models through their API.

## Key Features

- **Full model support**: Access to all available Grok models
- **OpenAI-compatible API**: Familiar interface for existing users
- **Async-first implementation**: Optimized for concurrent operations
- **Streaming support**: Real-time response handling
- **Usage tracking**: Detailed metrics and cost estimation

## Supported Models

```python
from aicore.models_metadata import METADATA

# List available Grok models
grok_models = [model for model in METADATA if model.startswith("grok-")]
print(grok_models)
```

## Configuration

### Python Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="grok",
    api_key="your_xai_api_key",
    model="grok-3",
    temperature=0.7,
    max_tokens=1000
)
```

### YAML Configuration

```yaml
provider: grok
api_key: "your_xai_api_key"
model: "grok-3"
temperature: 0.7
max_tokens: 1000
```

## Usage Examples

### Basic Completion

```python
from aicore.llm import Llm

llm = Llm(config=config)
response = llm.complete("Explain quantum computing in simple terms")
print(response)
```

### Usage Tracking

```python
usage = llm.get_usage()
print(f"Tokens used: {usage.total_tokens}")
print(f"Estimated cost: ${usage.estimated_cost:.4f}")
```

## Requirements

- xAI API key (available through xAI developer program)

## Limitations

- Currently only supports text completion (no chat interface)
- Limited model availability compared to other providers