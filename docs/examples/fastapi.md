# FastAPI Integration Guide

This guide demonstrates how to integrate AiCore's LLM capabilities with FastAPI to build production-ready AI applications, including Multi-Chat Platform (MCP) integration.

## Prerequisites

1. Python 3.9+
2. FastAPI and Uvicorn
3. AiCore package
4. For MCP integration: `fastmcp>=2.2.6`

## Installation

```bash
pip install fastapi uvicorn core-for-ai fastmcp
```

## Basic Setup

### Configuration File

Create a `config.yml` file:

```yaml
llm:
  provider: "openai"
  api_key: "YOur_api_key"
  model: "gpt-4o"
  temperature: 0.7
  max_tokens: 1000
```

### Minimal API Implementation

Create `main.py`:

```python
from fastapi import FastAPI
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

app = FastAPI()

# Initialize LLM from config
llm = Llm(config=LlmConfig.from_yaml("config.yml"))

@app.post("/chat")
async def chat(message: str):
    """Basic chat endpoint"""
    response = await llm.acomplete(message)
    return {"response": response}
```

Run the API:
```bash
uvicorn main:app --reload
```

## Advanced Features

### MCP (Multi-Chat Platform) Integration

First, create an MCP configuration file (`mcp_config.json`):

```json
{
  "mcpServers": {
    "brave-search": {
      "transport_type": "stdio",
      "command": "python",
      "args": ["-m", "brave_search.server"],
      "env": {
        "API_KEY": "YOur_api_key"
      }
    }
  }
}
```

Then implement MCP endpoints:

```python
from fastapi import APIRouter
from aicore.llm.mcp.client import MCPClient
from pathlib import Path

router = APIRouter()

@router.get("/tools")
async def list_tools():
    """List all available MCP tools"""
    async with MCPClient.from_config("mcp_config.json") as mcp:
        tools = await mcp.servers.tools
        return {"tools": [tool.dict() for tool in tools]}

@router.post("/call-tool/{tool_name}")
async def call_tool(tool_name: str, arguments: dict):
    """Call an MCP tool by name"""
    async with MCPClient.from_config("mcp_config.json") as mcp:
        result = await mcp.servers.call_tool(tool_name, arguments)
        return {"result": result}
```

### Authentication

Add JWT authentication using FastAPI's OAuth2:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta

# Configuration
SECRET_KEY = "YOur-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

@app.post("/secure-chat")
async def secure_chat(
    message: str,
    current_user: dict = Depends(get_current_user)
):
    """Authenticated chat endpoint"""
    response = await llm.acomplete(message)
    return {"response": response, "user": current_user}
```

### WebSocket Chat

Add real-time chat with WebSockets:

```python
from fastapi import WebSocket, WebSocketDisconnect
import json
from ulid import ulid

active_connections = {}
active_histories = {}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str = None):
    await websocket.accept()
    
    if not session_id:
        session_id = ulid()
    
    active_connections[session_id] = websocket
    history = active_histories.get(session_id, [])

    try:
        while True:
            data = await websocket.receive_text()
            history.append(data)
            
            response = []
            async for chunk in llm.acomplete(history, stream=True):
                await websocket.send_text(json.dumps({"chunk": chunk}))
                response.append(chunk)
            
            history.append("".join(response))
    
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]
```

### Rate Limiting

Add rate limiting middleware:

```python
from fastapi import Request
from fastapi.middleware import Middleware
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/limited-chat")
@limiter.limit("5/minute")
async def limited_chat(request: Request, message: str):
    """Rate-limited chat endpoint"""
    response = await llm.acomplete(message)
    return {"response": response}
```

## Production Deployment

### Docker Setup

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

Example deployment YAML:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aicore-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aicore-api
  template:
    metadata:
      labels:
        app: aicore-api
    spec:
      containers:
      - name: aicore-api
        image: YOur-registry/aicore-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: aicore-secrets
```

## Monitoring and Observability

Track LLM operations:

```python
from aicore.observability.collector import LlmOperationCollector

@app.get("/metrics")
async def get_metrics():
    """Get LLM operation metrics"""
    df = LlmOperationCollector.polars_from_db()
    return {
        "total_requests": len(df),
        "avg_latency": df["latency_ms"].mean(),
        "total_cost": df["cost"].sum()
    }
```

## Best Practices

1. Use environment variables for sensitive configuration
2. Implement proper error handling
3. Add request validation
4. Monitor token usage and costs
5. Use async endpoints for better performance
6. Implement proper logging
7. Set appropriate rate limits
8. Use HTTPS in production
9. For MCP integration:
   - Cache tool schemas to reduce startup time
   - Implement retry logic for tool calls
   - Monitor MCP server health