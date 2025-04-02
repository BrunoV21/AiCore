
<!--
  AiCore Project Usage Guide
  This document provides a detailed guide for using AiCore to interact with LLM and embedding providers.
-->

# Usage Instructions

Welcome to the usage guide for the AiCore Project. This page outlines the basic steps to install and start using AiCore for both text completions and embeddings, along with troubleshooting tips and configuration guidelines.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
  - [Synchronous Text Completion](#synchronous-text-completion)
  - [Asynchronous Text Completion](#asynchronous-text-completion)
  - [Generating Embeddings](#generating-embeddings)
- [Troubleshooting & Tips](#troubleshooting--tips)
- [Advanced Topics](#advanced-topics)

## Overview

AiCore provides a unified API for interacting with multiple language model (LLM) and embedding providers. It supports both synchronous and asynchronous operations, while also integrating advanced features like observability, logging, and reasoning augmentation.

## Installation

Install AiCore directly from GitHub using pip:

```bash
pip install git+https://github.com/BrunoV21/AiCore@0.1.9
```

Ensure you have a valid configuration file (in YAML format) set up as described in the Configuration section of the [Introduction](introduction.md).

## Basic Usage

### Synchronous Text Completion

The following example demonstrates how to perform synchronous text completion:

```python
from aicore.config import Config
from aicore.llm import Llm
import os

# Set the configuration file path
os.environ["CONFIG_PATH"] = "./config/config.yml"
config = Config.from_yaml()
llm = Llm.from_config(config.llm)

# Generate and print a completion
response = llm.complete("Explain the theory of relativity.")
print(response)
```

### Asynchronous Text Completion

For non-blocking operations, use the asynchronous API as shown below:

```python
import asyncio
from aicore.config import Config
from aicore.llm import Llm
import os

async def main():
    os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    response = await llm.acomplete("Describe how AI can transform healthcare.")
    print(response)

asyncio.run(main())
```

### Generating Embeddings

You can also generate text embeddings with AiCore:

```python
from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings import Embeddings

config = EmbeddingsConfig(
    provider="openai",
    api_key="your_api_key",
    model="your_embedding_model"
)
embeddings = Embeddings.from_config(config)
vectors = embeddings.generate(["Hello, how are you?"])
print(vectors)
```

## Troubleshooting & Tips

- Ensure your configuration file is correctly set up and the CONFIG_PATH environment variable is pointing to the right location.
- Verify that API keys for your provider are valid and active.
- For asynchronous operations, ensure your execution environment supports asyncio.
- Double-check the provider-specific settings in your configuration if you encounter issues.
- Refer to the [Advanced Topics](advanced_topics.md) for more in-depth troubleshooting and performance tuning guidelines.

## Advanced Topics

For detailed instructions on advanced configurations, reasoning augmentation, observability, and performance optimization, please refer to the [Advanced Topics](advanced_topics.md) documentation.

---

*This usage guide is a living document. Further details, examples, and updates will be added as the project evolves.*