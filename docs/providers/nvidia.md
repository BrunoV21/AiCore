
# NVIDIA Provider

The NVIDIA provider enables access to NVIDIA's AI Foundation Models and endpoints through the AiCore system.

## Supported Models

```python
from aicore.models_metadata import METADATA

# List available NVIDIA models
nvidia_models = [model for model in METADATA if model.startswith("nvidia/")]
print(nvidia_models)
```

## Key Features

- **NVIDIA AI Foundation Models**: Access to NVIDIA's hosted models
- **OpenAI-compatible API**: Consistent interface with other providers
- **Streaming Support**: Real-time response streaming
- **Usage Tracking**: Detailed metrics and cost tracking
- **Token Counting**: Automatic token usage calculation

## Configuration

### Python Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="nvidia",
    api_key="your_nvidia_api_key",
    model="nvidia/llama2-70b",
    temperature=0.7,
    max_tokens=1000
)
```

### YAML Configuration

```yaml
provider: nvidia
api_key: "your_nvidia_api_key"
model: "nvidia/llama2-70b"
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

## Advanced Features

### Custom Endpoints

```python
config = LlmConfig(
    provider="nvidia",
    api_key="your_api_key",
    model="nvidia/llama2-70b",
    base_url="https://your-custom-endpoint.nvidia.com"
)
```

For the most up-to-date pricing and quota information, refer to [NVIDIA's official documentation](https://developer.nvidia.com/ai-foundation-models).