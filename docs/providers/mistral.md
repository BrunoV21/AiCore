
# Mistral Provider

The Mistral provider enables access to Mistral AI's language models through the AiCore system, offering both chat and embedding capabilities.

## Features

- **Multiple Model Support**: Access all Mistral AI models through a unified interface
- **Streaming Support**: Real-time token streaming for chat completions
- **Token Counting**: Automatic token usage tracking
- **Cost Estimation**: Built-in cost calculation based on model pricing
- **Async/Sync APIs**: Both synchronous and asynchronous operation modes

## Supported Models

| Model Name       | Description                     | Context Window |
|------------------|---------------------------------|----------------|
| `mistral-tiny`   | Mistral 7B model               | 8k tokens      |
| `mistral-small`  | Mixtral 8x7B model             | 32k tokens     |
| `mistral-medium` | Latest medium-sized model      | 32k tokens     |
| `mistral-large`  | Latest large model (best performance) | 32k tokens |

## Configuration

### YAML Configuration

```yaml
llm:
  provider: mistral
  api_key: "your_mistral_api_key"
  model: "mistral-large"
  temperature: 0.7
  max_tokens: 1000
```

### Python Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="mistral",
    api_key="your_mistral_api_key",
    model="mistral-large",
    temperature=0.7,
    max_tokens=1000
)
```

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
for chunk in llm.stream("Write a poem about AI:"):
    print(chunk, end="", flush=True)
```

### Async Usage

```python
import asyncio
from aicore.llm import AsyncLlm

async def main():
    llm = AsyncLlm(config=config)
    response = await llm.acomplete("What is the capital of France?")
    print(response)

asyncio.run(main())
```

## Advanced Features

### Tool Calling

```python
response = llm.complete(
    "What's the weather in Paris?",
    tools=[{
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather",
            "parameters": {...}
        }
    }]
)
```

### JSON Mode

```python
response = llm.complete(
    "Return information about Paris in JSON format",
    response_format={"type": "json_object"}
)
```

## Observability Integration

All Mistral provider operations are automatically tracked by the AiCore observability system:

```python
from aicore.observability.collector import LlmOperationCollector

# View metrics for Mistral operations
mistral_metrics = LlmOperationCollector.polars_from_db(provider="mistral")
print(mistral_metrics.select(["model", "latency_ms", "total_tokens"]))
```

## Troubleshooting

**Common Issues:**
- `401 Unauthorized`: Verify your API key is correct
- `Model not found`: Check the model name spelling and your account access
- `Rate limit exceeded`: Implement retry logic or reduce request frequency

For additional help, refer to the [Mistral API documentation](https://docs.mistral.ai/).