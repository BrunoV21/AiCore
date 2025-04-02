
<!--
  AiCore Project Documentation
  This documentation provides a unified, formal guide for using AiCore,
  covering configuration, integrations with various LLM and embedding providers,
  advanced observability tools, and example applications.
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

Welcome to the AiCore Project Documentation.

AiCore provides a unified, extensible interface for interacting with multiple language model (LLM)
and embedding providers. It supports both synchronous and asynchronous operations, integrates advanced
reasoning capabilities, and includes a comprehensive observability module.

![Overview Image](path/to/overview_image.png) <!-- Placeholder for overview image -->

---

## QuickStart and Installation

This section explains how to install and configure AiCore.

### Installation

```bash
pip install git+https://github.com/BrunoV21/AiCore@0.1.9
```

### Configuration

Create a configuration file (e.g., `config/config.yml`) with your API keys and settings. For example:

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

Export the configuration path:

```bash
export CONFIG_PATH=./config/config.yml
```

---

## LLM Module

The LLM module offers a unified API for text completions and reasoning augmentation.

### Synchronous and Asynchronous Completions

Use the `complete` method for synchronous operations and `acomplete` for asynchronous requests:

```python
from aicore.config import Config
from aicore.llm import Llm
import os

os.environ["CONFIG_PATH"] = "./config/config.yml"
config = Config.from_yaml()
llm = Llm.from_config(config.llm)

# Synchronous completion
response = llm.complete("Explain the theory of relativity.")
print(response)

# Asynchronous completion
import asyncio
async def run():
    response = await llm.acomplete("Describe how AI transforms healthcare.")
    print(response)
asyncio.run(run())
```

### Reasoning Augmentation

AiCore supports automatic reasoning injection when a reasoner configuration exists.

```yaml
llm:
  provider: "mistral"
  api_key: "your_mistral_api_key"
  model: "mistral-small-latest"
  reasoner:
    provider: "groq"
    api_key: "your_groq_api_key"
    model: "deepseek-r1-distill-llama-70b"
    temperature: 0.5
    max_tokens: 1024
```

![LLM Flow Diagram](path/to/llm_flow_diagram.png) <!-- Placeholder for diagram image -->

---

## Logging Module

The logging module leverages Loguru to capture, format, and stream logs.

Logs can be recorded to files with daily rotations and streamed to the console.

```python
from aicore.logger import _logger
_logger.logger.info("This is a log message.")
```

![Logging Screenshot](path/to/logging_screenshot.png) <!-- Placeholder for logging screenshot -->

---

## Observability Module

This module collects detailed metrics on LLM operations including token usage, latency, and cost.

An interactive dashboard built with Dash and Plotly helps visualize these metrics.

```python
from aicore.observability import ObservabilityDashboard
dashboard = ObservabilityDashboard(storage_path="path/to/llm_operations.json")
dashboard.run_server(debug=True, port=8050)
```

![Dashboard Screenshot](path/to/dashboard_screenshot.png) <!-- Placeholder for dashboard image -->

---

## Chainlit Example

Integrate AiCore with Chainlit for interactive applications.

Example snippet:

```python
import chainlit as cl
from aicore.llm import Llm

@cl.on_chat_start
async def start_chat():
    llm = Llm.from_config(...)  # Initialize with proper config
    cl.user_session.set("llm", llm)
    await cl.Message(content="Chat session started!").send()

@cl.on_message
async def handle_message(message: cl.Message):
    llm = cl.user_session.get("llm")
    response = llm.complete(message.content, stream=True)
    await cl.Message(content=response).send()
```

![Chainlit Example](path/to/chainlit_example.png) <!-- Placeholder for chainlit example image -->

---

## FastAPI Example

Deploy AiCore using FastAPI with RESTful and WebSocket endpoints.

Example snippet:

```python
from fastapi import FastAPI, WebSocket
from aicore.llm import Llm

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    llm = Llm.from_config(...)  # Initialize with proper config
    while True:
        data = await websocket.receive_text()
        response = llm.complete(data, stream=True)
        for token in response.split():
            await websocket.send_text(token)
```

![FastAPI Example](path/to/fastapi_example.png) <!-- Placeholder for FastAPI example image -->

---

For further details, refer to the individual sections and example configurations.