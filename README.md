# AiCore Project

This project provides a framework for integrating various language models and embedding providers. It supports both synchronous and asynchronous operations for generating text completions and embeddings. The current implementation includes support for OpenAI and Mistral providers.

## Installation

To install the required dependencies, run:
```bash
pip install -r requirements.txt
```

## Usage

### Language Models

You can use the language models to generate text completions. Below is an example of how to use the `MistralLlm` provider:

```python
from aicore.llm.config import LlmConfig
from aicore.llm.providers import MistralLlm

config = LlmConfig(
    api_key="your_api_key",
    model="your_model_name",
    temperature=0.7,
    max_tokens=100
)

mistral_llm = MistralLlm.from_config(config)
response = mistral_llm.complete(prompt="Hello, how are you?")
print(response)
```

### Embeddings

You can use the embeddings module to generate text embeddings. Below is an example of how to use the `OpenAiEmbeddings` provider:

```python
from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings import Embeddings

config = EmbeddingsConfig(
    provider="openai",
    api_key="your_api_key",
    model="your_model_name"
)

embeddings = Embeddings.from_config(config)
vectors = embeddings.generate(["Hello, how are you?"])
print(vectors)
```

For asynchronous usage:

```python
import asyncio
from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings import Embeddings

async def main():
    config = EmbeddingsConfig(
        provider="openai",
        api_key="your_api_key",
        model="your_model_name"
    )

    embeddings = Embeddings.from_config(config)
    vectors = await embeddings.agenerate(["Hello, how are you?"])
    print(vectors)

asyncio.run(main())
```

### Loading from a Config File

To load configurations from a YAML file, set the `CONFIG_PATH` environment variable and use the `Config` class to load the configurations. Here is an example:

```python
from aicore.config import Config
from aicore.llm import Llm
import os

if __name__ == "__main__":
    os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    llm.complete("Once upon a time, there was a")
```

Make sure your `config.yml` file is properly set up with the necessary configurations.

## License

This project is licensed under the MIT License.