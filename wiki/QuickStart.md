
# QuickStart and Installation

Welcome to the quick start guide for the AiCore Project. This document provides step-by-step instructions to install, configure, and run AiCore for interacting with various language model (LLM) and embedding providers.

## 1. Installation

To install AiCore, run:

```bash
pip install git+https://github.com/BrunoV21/AiCore@0.1.9
```

## 2. Configuration

Before using AiCore, create a configuration file (e.g., `config/config.yml`) with your API keys and desired settings. An example configuration:

```yaml
embeddings:
  provider: "openai"        # Options: "openai", "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_key"
  model: "your_embedding_model"

llm:
  provider: "openai"         # Options: "openai", "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_key"
  model: "gpt-4o-mini"        # Replace with the appropriate model
  temperature: 0.1
  max_tokens: 1028
```

Set the environment variable `CONFIG_PATH` to point to your configuration file:

```bash
export CONFIG_PATH=./config/config.yml
```

## 3. Running AiCore

Once configured, you can initialize and use the language model interface. For example:

```python
from aicore.config import Config
from aicore.llm import Llm
import os

os.environ["CONFIG_PATH"] = "./config/config.yml"
config = Config.from_yaml()
llm = Llm.from_config(config.llm)

# Generate a text completion
response = llm.complete("Once upon a time")
print(response)
```

### Asynchronous Example

For non-blocking operations, you can use the asynchronous API:

```python
import asyncio
from aicore.config import Config
from aicore.llm import Llm
import os

async def main():
    os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    response = await llm.acomplete("Tell me a story about AI.")
    print(response)

asyncio.run(main())
```

## 4. Next Steps

- For detailed documentation on logging, see [Logging Module](Logging.md).
- Learn how to work with the LLM functionalities in the [LLM Module](LLM.md).
- Explore observability data in the [Observability Module](Observability.md).
- Check out examples in the [Chainlit Example](Chainlit-Example.md) and [FastAPI Example](FastAPI-Example.md).

Enjoy working with AiCore!