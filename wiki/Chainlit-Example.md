
# AiCore Chainlit Example

This document provides a minimal example of how to integrate AiCore into a Chainlit application. It covers the necessary setup, initialization, and a simple code snippet to demonstrate prompt handling and streaming responses.

## Installation

1. Install AiCore from GitHub:

   ```bash
   pip install git+https://github.com/BrunoV21/AiCore
   ```

2. Install Chainlit (ensure you have version 2.0.dev1 or later):

   ```bash
   pip install chainlit==2.0.dev1
   ```

## Example Setup

Below is a basic Chainlit application using AiCore:

```python
import chainlit as cl
from aicore.config import Config
from aicore.llm import Llm

@cl.on_chat_start
async def start_chat():
    # Load configuration from a YAML file.
    config = Config.from_yaml("./config/config.yml")
    llm = Llm.from_config(config.llm)
    cl.user_session.set("llm", llm)
    await cl.Message(content="Chat session started.").send()

@cl.on_message
async def main(message: cl.Message):
    # Retrieve the LLM instance from the session.
    llm = cl.user_session.get("llm")
    # Process the user's message with streaming enabled.
    response = llm.complete(message.content, stream=True)
    await cl.Message(content=response).send()

# Additional instructions:
# - The example uses synchronous completion for simplicity.
# - For asynchronous streaming, consider using llm.acomplete with appropriate async handling.
```

## Explanation

- **Initialization:** On chat start, the AiCore LLM provider is configured using a YAML file.
- **Session Storage:** The LLM instance is stored in the Chainlit session for subsequent user interactions.
- **Message Handling:** Each incoming message is processed using the `complete` method with streaming enabled, and the generated response is sent back to the user.

For further details, consult the main [AiCore documentation](../README.md) and explore additional examples.