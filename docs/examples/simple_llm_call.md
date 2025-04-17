
# Simple LLM Call Example

This guide demonstrates how to make a simple LLM call using AiCore's LLM interface.

## Prerequisites

1. Python 3.8+
2. AiCore installed (`pip install aicore`)
3. API key for your chosen LLM provider

## Step 1: Import Required Modules

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig
```

## Step 2: Configure the LLM

Create a configuration for your LLM provider. Here's an example for OpenAI:

```python
config = LlmConfig(
    provider="openai",
    api_key="your_api_key_here",  # Replace with your actual API key
    model="gpt-4o",              # Model name
    temperature=0.7,             # Creativity level (0-1)
    max_tokens=1000              # Maximum response length
)
```

Alternatively, you can load configuration from a YAML file:

```python
from aicore.config import Config

config = Config.from_yaml("path/to/config.yml").llm
```

Example YAML configuration (`config.yml`):
```yaml
llm:
  provider: "openai"
  api_key: "your_api_key_here"
  model: "gpt-4o"
  temperature: 0.7
  max_tokens: 1000
```

## Step 3: Initialize the LLM

```python
llm = Llm(config=config)
```

## Step 4: Make a Simple Completion Call

### Synchronous Call

```python
response = llm.complete("Explain quantum computing in simple terms")
print(response)
```

### Asynchronous Call

```python
import asyncio

async def get_response():
    response = await llm.acomplete("Explain quantum computing in simple terms")
    print(response)

asyncio.run(get_response())
```

## Step 5: Handle Streaming Responses (Default)

By default, responses are streamed:

```python
response = llm.complete("Tell me a story about AI")
# Response will stream to stdout in real-time
```

To disable streaming:

```python
response = llm.complete("Tell me a story about AI", stream=False)
```

## Step 6: Using System Prompts

```python
response = llm.complete(
    "Write a poem about technology",
    system_prompt="You are a creative poet specializing in haikus"
)
```

## Step 7: Working with JSON Output

```python
response = llm.complete(
    "List the top 3 programming languages with their main features as JSON",
    json_output=True
)
print(response)  # Returns a parsed dictionary
```

## Step 8: Monitoring Usage

```python
print(llm.usage)  # Shows current session usage

# Example output:
# Total | Cost: $0.0023 | Tokens: 342 | Prompt: 120 | Response: 222
```

## Complete Example

Here's a complete working example:

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

# Configuration
config = LlmConfig(
    provider="openai",
    api_key="your_api_key_here",
    model="gpt-4o",
    temperature=0.7,
    max_tokens=1000
)

# Initialize LLM
llm = Llm(config=config)

# Make completion
response = llm.complete("Explain quantum computing in simple terms")
print(response)

# Print usage
print("\nUsage Stats:")
print(llm.usage)
```

## Troubleshooting

1. **Authentication Errors**: Verify your API key is correct
2. **Model Not Found**: Check the model name matches your provider's available models
3. **Rate Limits**: Implement retry logic or check your provider's quota

For more advanced usage, see the [LLM documentation](../llm/overview.md).