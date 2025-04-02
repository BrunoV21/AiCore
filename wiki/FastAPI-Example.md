
# FastAPI Example

This guide demonstrates how to serve AiCore via FastAPI with a WebSocket endpoint for real-time streaming responses.

## Overview

In this example, we build a simple FastAPI microservice that:
- Provides a REST endpoint for health checking.
- Offers a WebSocket endpoint to stream LLM responses as they are generated.
- Integrates with the AiCore framework to access LLM functionalities.

## Setup

1. **Install Dependencies**

   ```bash
   pip install fastapi uvicorn websockets
   pip install git+https://github.com/BrunoV21/AiCore@0.1.9
   ```

2. **Configuration**

   - Set the `CONFIG_PATH` environment variable to point to your YAML configuration file.
   - Configure your API keys and model settings in the config file (e.g., `config/config.yml`).

## Code Example

Below is a basic scaffold of a FastAPI application integrated with AiCore and a WebSocket endpoint for streaming:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import os

from aicore.config import Config
from aicore.llm import Llm

app = FastAPI(title="AiCore FastAPI Example")

@app.on_event("startup")
async def startup_event():
    # Set up configuration and initialize LLM
    os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    # Initialize and store the LLM instance in application state
    app.state.llm = Llm.from_config(config.llm)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    llm = app.state.llm
    # Optionally, assign the session_id to the LLM instance
    llm.session_id = session_id
    try:
        while True:
            # Read incoming message from the client
            data = await websocket.receive_text()
            # Call the LLM provider in streaming mode
            response = llm.complete(data, stream=True)
            # For simplicity, split the response and send tokens one by one
            for token in response.split():
                await websocket.send_text(token)
    except WebSocketDisconnect:
        print(f"WebSocket connection closed for session: {session_id}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Running the Server

Execute the server with:

```bash
uvicorn main:app --reload
```

You can access the interactive API docs at `http://localhost:8000/docs`.

## Additional Enhancements

- **Error Handling & Robustness:** In a production setup, consider adding error handling and reconnect logic to manage unexpected disconnections.
- **Authentication:** Secure your WebSocket endpoints by integrating authentication and authorization as needed.
- **Advanced Configuration:** Leverage environment variables and YAML-based configuration files to dynamically adjust settings for different deployment environments.

## Conclusion

This guide provides an initial scaffold for integrating AiCore with FastAPI to offer real-time LLM streaming via a WebSocket interface. Further enhancements—such as improved error handling, security measures, and extended configuration options—can be added to suit advanced use cases and production requirements.

---

*This document serves as an initial guide. Future updates will provide more detailed examples and extended configurations as the project evolves.*