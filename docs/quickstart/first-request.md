
# Making Your First Request

This guide walks you through making your first LLM request using AiCore.

## Prerequisites

- Completed [installation](installation.md)
- Valid API key for your chosen provider
- Basic Python knowledge

## Basic Usage

1. First, import the required modules:

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig
```

2. Configure your LLM provider (example using OpenAI):

```python
config = LlmConfig(
    provider="openai",
    api_key="your_api_key_here",
    model="gpt-3.5-turbo"
)
```

3. Initialize the LLM client:

```python
llm = Llm(config=config)
```

4. Make your first request:

```python
response = llm.complete("Hello world!")
print(response)
```

## Async Usage

For asynchronous applications:

```python
import asyncio
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

async def main():
    config = LlmConfig(
        provider="openai",
        api_key="your_api_key_here",
        model="gpt-3.5-turbo"
    )
    llm = Llm(config=config)
    
    response = await llm.acomplete("Hello async world!")
    print(response)

asyncio.run(main())
```

## Configuration Options

You can customize your requests with:

- `temperature`: Controls randomness (0-1)
- `max_tokens`: Limits response length
- `stream`: Enables streaming responses

Example with custom settings:

```python
response = llm.complete(
    "Explain quantum computing",
    temperature=0.7,
    max_tokens=500,
    stream=True
)
```

## Next Steps

- Learn about [advanced configuration](../config/llmconfig.md)
- Explore [provider-specific features](../providers/)
- Check out [usage tracking](../llm/usage.md) for cost monitoring
- Try the [examples](../examples/README.md) for more complex scenarios