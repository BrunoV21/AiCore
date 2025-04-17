
# Simple Async LLM Call Example

This example demonstrates how to make asynchronous LLM calls using AiCore's async interface. Async calls are recommended for web applications and other I/O-bound workloads.

## Prerequisites

1. Python 3.8+
2. AiCore installed (`pip install aicore`)
3. API key for your chosen LLM provider

## Step 1: Configuration

First, create a configuration file (`config.yml`) or set environment variables:

```yaml
# config.yml example for OpenAI
llm:
  provider: "openai"
  api_key: "your_api_key_here"
  model: "gpt-4o"
  temperature: 0.7
  max_tokens: 1000
```

Alternatively, set environment variables:
```bash
export LLM_PROVIDER=openai
export LLM_API_KEY=your_api_key_here
export LLM_MODEL=gpt-4o
export LLM_TEMPERATURE=0.7
export LLM_MAX_TOKENS=1000
```

## Step 2: Basic Async Call

Here's a simple async example:

```python
import asyncio
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

async def main():
    # Initialize LLM (config can be from file, env vars, or direct)
    config = LlmConfig(
        provider="openai",
        api_key="your_api_key_here",
        model="gpt-4o"
    )
    llm = Llm(config=config)
    
    # Make async call
    response = await llm.acomplete("Explain quantum computing in simple terms")
    print(response)

# Run the async function
asyncio.run(main())
```

## Step 3: Streaming Responses

For real-time streaming of responses:

```python
import asyncio
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

async def main():
    config = LlmConfig(
        provider="openai",
        api_key="your_api_key_here",
        model="gpt-4o"
    )
    llm = Llm(config=config)
    
    # Stream response in real-time
    response = await llm.acomplete(
        "Write a poem about artificial intelligence",
        stream=True  # Streaming is enabled by default
    )
    # Response will be printed as it streams
    print(response)

asyncio.run(main())
```

## Step 4: With System Prompt

Add a system prompt to guide the model's behavior:

```python
import asyncio
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

async def main():
    config = LlmConfig(
        provider="openai",
        api_key="your_api_key_here",
        model="gpt-4o"
    )
    llm = Llm(config=config)
    
    response = await llm.acomplete(
        "Recommend some books about machine learning",
        system_prompt="You are a helpful librarian with expertise in technical books"
    )
    print(response)

asyncio.run(main())
```

## Step 5: Error Handling

Proper error handling for async calls:

```python
import asyncio
from aicore.llm import Llm
from aicore.llm.config import LlmConfig
from aicore.models import AuthenticationError, ModelError

async def main():
    try:
        config = LlmConfig(
            provider="openai",
            api_key="invalid_key",
            model="gpt-4o"
        )
        llm = Llm(config=config)
        
        response = await llm.acomplete("Hello world")
        print(response)
        
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
    except ModelError as e:
        print(f"Model error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(main())
```

## Step 6: Advanced Usage - Multiple Async Calls

Run multiple async calls concurrently:

```python
import asyncio
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

async def ask_question(llm: Llm, question: str):
    response = await llm.acomplete(question)
    print(f"Q: {question}\nA: {response}\n")

async def main():
    config = LlmConfig(
        provider="openai",
        api_key="your_api_key_here",
        model="gpt-4o"
    )
    llm = Llm(config=config)
    
    questions = [
        "What is the capital of France?",
        "Explain the theory of relativity",
        "What are the benefits of Python?"
    ]
    
    # Run all questions concurrently
    tasks = [ask_question(llm, q) for q in questions]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

## Best Practices

1. **Reuse LLM instances**: Initialize once and reuse across requests
2. **Set timeouts**: Use `asyncio.wait_for` for request timeouts
3. **Monitor usage**: Check `llm.usage` for token counts and costs
4. **Error handling**: Always wrap calls in try/except blocks
5. **Streaming**: Use streaming for better user experience with long responses

## Next Steps

- Explore [FastAPI integration](../fastapi.md) for web applications
- Learn about [reasoning augmentation](../reasoning_example.md)
- Check [observability features](../../observability/overview.md) for monitoring