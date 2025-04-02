
# LLM Module

This document provides a high-level guide on using the LLM module in the AiCore project. It focuses on the primary functionalities offered by the module as defined in `aicore/llm/llm.py`, without delving into provider-specific details.

## Overview

The LLM module provides a unified interface for interacting with various large language models. It supports:
- **Synchronous completions** via the `complete` method.
- **Asynchronous completions** via the `acomplete` method.
- **Reasoning augmentation** by optionally configuring a reasoner.

## Synchronous Completions

To generate text synchronously:

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

# Configure your LLM (adjust provider, api_key, and model as needed)
config = LlmConfig(
    provider="openai",
    api_key="YOUR_API_KEY",
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=8192
)

# Initialize an LLM instance
llm = Llm.from_config(config)

# Generate a completion
response = llm.complete("Explain the theory of relativity.")
print(response)
```

## Asynchronous Completions

For non-blocking operations, use the asynchronous API:

```python
import asyncio
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

async def run_async():
    config = LlmConfig(
        provider="openai",
        api_key="YOUR_API_KEY",
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=8192
    )
    llm = Llm.from_config(config)
    response = await llm.acomplete("Describe how AI can transform healthcare.")
    print(response)

asyncio.run(run_async())
```

## Reasoning Augmentation

AiCore can augment completions with additional reasoning steps if a reasoner is configured. To enable this feature:
- Define a reasoner configuration within your main LLM settings (using the `reasoner` field).
- The module automatically injects reasoning prompts into the completion process.

Example configuration snippet:

```yaml
llm:
  provider: "mistral"
  api_key: "YOUR_MISTRAL_API_KEY"
  model: "mistral-small-latest"
  temperature: 0
  max_tokens: 8192
  reasoner:
    provider: "groq"
    api_key: "YOUR_GROQ_API_KEY"
    model: "deepseek-r1-distill-llama-70b"
    temperature: 0.5
    max_tokens: 1024
```

With this setup, calls to `complete` or `acomplete` will automatically include reasoning steps.

## Additional Notes

- The LLM module abstracts away the low-level details of interacting with multiple providers.
- For advanced configurations, refer to the provider-specific documentation.
- This guide serves as an initial scaffold for getting started with LLM operations in AiCore.