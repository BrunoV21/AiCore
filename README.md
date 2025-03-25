
# AiCore Project
[![GitHub Stars](https://img.shields.io/github/stars/BrunoV21/AiCore?style=social)](https://github.com/BrunoV21/AiCore/stargazers)
[![GitHub Downloads](https://img.shields.io/github/downloads/BrunoV21/AiCore/total?color=blue)](https://github.com/BrunoV21/AiCore/releases)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/core-for-ai?style=flat)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)

This project provides a framework for integrating various language models and embedding providers. It supports both synchronous and asynchronous operations for generating text completions and embeddings. 

AiCore also contains native support to augment *traditional* Llms with *reasoning* capabilities by providing them with the thinking steps generated by an open-source reasoning capable model, allowing it to generate its answers in a Reasoning Augmented way. 

This can be usefull in multiple scenarios, such as:
- ensure your agentic systems still work with the propmts you have crafted for your favourite llms while augmenting them with reasoning steps
- direct control for how long you want your reasoner to reason (via max_tokens param) and how creative it can be (reasoning temperature decoupled from generation temperature) without compromising generation settings

## New Feature: Observability Module

AiCore now includes a comprehensive observability module that helps you track, analyze, and visualize your LLM operations:

- **Data Collection**: Automatically captures detailed information about each LLM completion operation, including arguments, responses, token usage, and latency metrics.
- **Interactive Dashboard**: A Dash/Plotly-based dashboard for visualizing operation history, performance trends, and usage patterns.
- **Efficient Storage**: Uses Polars dataframes for high-performance data processing and storage in JSON format.
- **Complete Integration**: Seamlessly integrated with the existing LLM provider system.

To use the observability dashboard:

```python
from aicore.observability import ObservabilityDashboard

dashboard = ObservabilityDashboard(storage=storage)

# Run the dashboard server
dashboard.run_server(debug=True, port=8050)
```

## Built with AiCore

**Reasoner4All**
A Hugging Face Space where you can chat with multiple reasoning augmented models.

[![Hugging Face Space](https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-xl.svg)](https://huggingface.co/spaces/McLoviniTtt/Reasoner4All)

**CodeGraph**
A Graph representation of your codebase for effective retrieval at file/obj level *coming soon*

## Quickstart
```bash
pip install git+https://github.com/BrunoV21/AiCore@0.1.9
```

## Features
**LLM Providers:**
- Anthropic
- OpenAI
- Mistral
- Groq
- Gemini
- Nvidia
- OpenRouter

**Embedding Providers:**
- OpenAI
- Mistral
- Groq
- Gemini
- Nvidia

**Observability Tools:**
- Operation tracking and metrics collection
- Interactive dashboard for visualization
- Token usage and latency monitoring

To configure the application for testing, you need to set up a `config.yml` file with the necessary API keys and model names for each provider you intend to use. The `CONFIG_PATH` environment variable should point to the location of this file. Here's an example of how to set up the `config.yml` file:

```yaml
# config.yml
embeddings:
  provider: "openai" # or "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_api_key"
  model: "your_openai_embedding_model" # Optional

llm:
  provider: "openai" # or "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_api_key"
  model: "gpt-4o" # Optional
  temperature: 0.1
  max_tokens: 1028
```

**Reasoner Augmented Config**

To leverage the reasoning augmentation just introduce one of the supported llm configs into the reasoner field and AiCore handles the rest

```yaml
# config.yml
embeddings:
  provider: "openai" # or "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_api_key"
  model: "your_openai_embedding_model" # Optional

llm:
  provider: "mistral" # or "openai", "groq", "gemini", "nvidia"
  api_key: "your_mistral_api_key"
  model: "mistral-small-latest" # Optional
  temperature: 0.6
  max_tokens: 2048
  reasoner:
    provider: "groq" # or openrouter or nvidia
    api_key: "your_groq_api_key"
    model: "deepseek-r1-distill-llama-70b" # or "deepseek/deepseek-r1:free" or "deepseek/deepseek-r1"
    temperature: 0.5
    max_tokens: 1024
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

This project is licensed under the Apache 2.0 License.
