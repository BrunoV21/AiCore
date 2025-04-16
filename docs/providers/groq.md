
# Groq Provider

The Groq provider enables access to Groq's ultra-fast LLM inference engine with support for various open-weight models.

## Supported Models

```python
from aicore.models_metadata import METADATA

# List available Groq models
groq_models = [model for model in METADATA if model.startswith("groq-")]
print(groq_models)
```

## Configuration

### YAML Configuration
```yaml
provider: groq
api_key: "your_api_key_here"  # Get from Groq console
model: "mixtral-8x7b-32768"   # Default model
temperature: 0.7              # Optional
max_tokens: 1024              # Optional
```

### Python Configuration
```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="groq",
    api_key="your_api_key_here",
    model="mixtral-8x7b-32768",
    temperature=0.7,
    max_tokens=1024
)
```

## Key Features

- **Ultra-low latency**: Optimized for high-speed inference
- **Streaming support**: Real-time token streaming
- **Cost tracking**: Automatic token counting and cost estimation
- **Multiple model support**: Access to various open-weight models

## Usage Examples

### Basic Completion
```python
from aicore.llm import Llm

llm = Llm(config=config)
response = llm.complete("Explain quantum computing in simple terms")
print(response)
```

### Streaming Response
```python
async for chunk in llm.stream("Tell me about Groq's architecture"):
    print(chunk, end="", flush=True)
```

### Advanced Usage
```python
# With conversation history
messages = [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "What's the weather today?"}
]

response = llm.chat_complete(messages)
```

## Best Practices

1. **Model Selection**: Choose the appropriate model for your use case:
   - `mixtral-8x7b-32768`: General purpose
   - `llama2-70b-4096`: Larger context window

2. **Performance Tuning**:
   - Adjust `temperature` for creativity vs consistency
   - Set `max_tokens` to control response length

3. **Error Handling**:
   - The provider implements automatic retries for transient errors
   - See [retry mechanism](../llm/retry.md) for details

For advanced usage, refer to the [base provider documentation](../llm/base_provider.md).