
<!--
  AiCore Project Documentation
  A unified guide for using AiCore with multiple LLM and embedding providers.
  This documentation is hosted on GitHub Pages.
-->

# AiCore Project Documentation

![Project Logo](path/to/logo.png) <!-- Placeholder for project logo image -->

## Table of Contents
1. [Home](#home)
2. [QuickStart and Installation](#quickstart-and-installation)
3. [LLM Module](#llm-module)
4. [Logging Module](#logging-module)
5. [Observability Module](#observability-module)
6. [Chainlit Example](#chainlit-example)
7. [FastAPI Example](#fastapi-example)

---

## Home

Welcome to the AiCore Project—a unified framework for interacting with multiple language models and embedding providers.

AiCore provides a consistent API for synchronous and asynchronous operations. It also integrates advanced observability tools to monitor LLM performance.

![Overview Image](path/to/overview_image.png) <!-- Placeholder for overview image -->

---

## QuickStart and Installation

This section walks you through the installation and initial setup.

### Installation

Install AiCore using:

```bash
pip install git+https://github.com/BrunoV21/AiCore@0.1.9
```

### Configuration

Create a YAML configuration file (e.g., `config/config.yml`) with your API keys and model settings. For example:

```yaml
embeddings:
  provider: "openai"
  api_key: "your_openai_api_key"
  model: "your_embedding_model"

llm:
  provider: "openai"
  api_key: "your_openai_api_key"
  model: "gpt-4o-mini"
  temperature: 0.1
  max_tokens: 1028
```

Set the environment variable to point to your configuration file:

```bash
export CONFIG_PATH=./config/config.yml
```

---

## LLM Module

The LLM module provides a unified interface for text completions and reasoning augmentation.

### Synchronous and Asynchronous Operations

Use the `complete` method for synchronous completions:

```python
from aicore.config import Config
from aicore.llm import Llm
import os

os.environ["CONFIG_PATH"] = "./config/config.yml"
config = Config.from_yaml()
llm = Llm.from_config(config.llm)
response = llm.complete("Explain the theory of relativity.")
print(response)
```

For asynchronous completions, use `acomplete`:

```python
import asyncio
from aicore.config import Config
from aicore.llm import Llm

async def main():
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    response = await llm.acomplete("Describe how AI can transform healthcare.")
    print(response)

asyncio.run(main())
```

### Reasoning Augmentation

AiCore can inject additional reasoning steps if a reasoner is configured. Simply include a reasoner configuration in your YAML file:

```yaml
llm:
  provider: "mistral"
  api_key: "your_mistral_api_key"
  model: "mistral-small-latest"
  temperature: 0
  max_tokens: 2048
  reasoner:
    provider: "groq"
    api_key: "your_groq_api_key"
    model: "deepseek-r1-distill-llama-70b"
    temperature: 0.5
    max_tokens: 1024
```

---

## Logging Module

The logging module leverages Loguru to capture and stream logs during LLM operations. It supports:

- File-based logging with daily rotations
- Real-time console logging
- Session-specific log queues to track individual LLM operations

![Logging Screenshot](path/to/logging_screenshot.png) <!-- Placeholder for logging screenshot -->

For further details, review the [Logging Module](Logging.md) documentation.

---

## Observability Module

The Observability Module collects metrics and enables visualization of the performance and usage of LLM operations.

Key features include:

- Detailed operation tracking (latency, token usage, cost)
- Storage options: JSON file or SQL database persistence
- Interactive dashboards built with Dash and Plotly for real-time analysis

![Dashboard Screenshot](path/to/dashboard_screenshot.png) <!-- Placeholder for dashboard image -->

To launch the dashboard:

```python
from aicore.observability import ObservabilityDashboard
dashboard = ObservabilityDashboard(storage_path="path/to/llm_operations.json")
dashboard.run_server(debug=True, port=8050)
```

For more information, see [Observability Module](Observability.md).

---

## Chainlit Example

Integrate AiCore with Chainlit to build interactive chat applications.

### Example

```python
import chainlit as cl
from aicore.config import Config
from aicore.llm import Llm
import os

@cl.on_chat_start
async def start_chat():
    os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    cl.user_session.set("llm", llm)
    await cl.Message(content="Chat session started.").send()

@cl.on_message
async def handle_message(message: cl.Message):
    llm = cl.user_session.get("llm")
    response = llm.complete(message.content, stream=True)
    await cl.Message(content=response).send()
```

![Chainlit Example](path/to/chainlit_example.png) <!-- Placeholder for Chainlit example image -->

---

## FastAPI Example

Deploy AiCore using FastAPI to provide both RESTful and WebSocket endpoints.

### Example

```python
from fastapi import FastAPI, WebSocket
from aicore.config import Config
from aicore.llm import Llm
import os

os.environ["CONFIG_PATH"] = "./config/config.yml"
config = Config.from_yaml()
llm = Llm.from_config(config.llm)

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        response = llm.complete(data, stream=True)
        for token in response.split():
            await websocket.send_text(token)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

![FastAPI Example](path/to/fastapi_example.png) <!-- Placeholder for FastAPI example image -->

---

For detailed documentation and further examples, refer to the individual pages:
- [QuickStart and Installation](QuickStart.md)
- [LLM Module](LLM.md)
- [Logging Module](Logging.md)
- [Observability Module](Observability.md)
- [Chainlit Example](Chainlit-Example.md)
- [FastAPI Example](FastAPI-Example.md)