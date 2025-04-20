
# FastAPI Integration Guide

This guide demonstrates how to integrate AiCore's LLM capabilities with FastAPI to build production-ready AI applications.

## Prerequisites

1. Python 3.9+
2. FastAPI and Uvicorn
3. AiCore package

## Installation

```bash
pip install fastapi uvicorn core-for-ai
```

## Basic Setup

### Configuration File

Create a `config.yml` file:

```yaml
llm:
  provider: "openai"
  api_key: "your_api_key"
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

### Authentication

Add JWT authentication using FastAPI's OAuth2:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta

# Configuration
SECRET_KEY = "your-secret-key"
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
### helper functions
llm_sessions: Dict[str, Llm] = {}

async def initialize_llm_session(session_id: str, config: Optional[LlmConfig] = None) -> Llm:
    """
    Initialize or retrieve an LLM session
    
    Args:
        session_id: The session identifier
        config: Optional custom LLM configuration
        
    Returns:
        An initialized LLM instance
    """
    if session_id in llm_sessions:
        return llm_sessions[session_id]
    
    try:
        # Initialize LLM based on whether custom config is provided
        if config:
            # Convert Pydantic model to dict and use for LLM initialization
            config_dict = config.dict(exclude_none=True)
            llm = Llm.from_config(config_dict)
        else:
            # Use the default configuration from environment
            os.environ["CONFIG_PATH"] = CONFIG_PATH
            config = Config.from_yaml()
            llm = Llm.from_config(config.llm)
        llm.session_id = session_id
        llm_sessions[session_id] = llm
        return llm
    except Exception as e:
        print(f"Error initializing LLM for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize LLM: {str(e)}")

def trim_messages(messages, tokenizer_fn, max_tokens :Optional[int]=None):
    max_tokens = max_tokens or int(os.environ.get("MAX_HISTORY_TOKENS", 16000))
    while messages and sum(len(tokenizer_fn(msg)) for msg in messages) > max_tokens:
        messages.pop(0)  # Remove from the beginning
    return messages
    
async def run_concurrent_tasks(llm, message):
    asyncio.create_task(llm.acomplete(message))
    asyncio.create_task(_logger.distribute())
    # Stream logger output while LLM is running
    while True:        
        async for chunk in _logger.get_session_logs(llm.session_id):
            yield chunk  # Yield each chunk directly
```

```python
### websocket endpoint
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
from typing import Optional

from services.llm_service import initialize_llm_session, trim_messages, run_concurrent_tasks
from aicore.const import SPECIAL_TOKENS, STREAM_END_TOKEN
import ulid

router = APIRouter()

# WebSocket connection storage
active_connections = {}
active_histories = {}

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id : Optional[str]=None):
    await websocket.accept()

    if not session_id:
        session_id = ulid.ulid()
    
    # Store the connection
    active_connections[session_id] = websocket

    history  = []
    try:
        # Initialize LLM
        llm = await initialize_llm_session(session_id)
        if session_id not in active_histories:
            active_histories[session_id] = history
        else:
            history = active_histories[session_id]
        
        while True:
            data = await websocket.receive_text()
            message = data
            history.append(message)
            history = trim_messages(history, llm.tokenizer)
            response = []
            async for chunk in run_concurrent_tasks(
                llm,
                message=history
            ):
                if chunk == STREAM_END_TOKEN:
                    break
                elif chunk in SPECIAL_TOKENS:
                    continue
                
                await websocket.send_text(json.dumps({"chunk": chunk}))
                response.append(chunk)
            
            history.append("".join(response))
    
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]
    except Exception as e:
        if session_id in active_connections:
            await websocket.send_text(json.dumps({"error": str(e)}))
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

### Session Management

Track conversations with session IDs:

```python
from uuid import uuid4
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str = None

@app.post("/session-chat")
async def session_chat(request: ChatRequest):
    """Chat endpoint with session tracking"""
    if not request.session_id:
        request.session_id = str(uuid4())
    
    llm.session_id = request.session_id
    response = await llm.acomplete(request.message)
    
    return {
        "response": response,
        "session_id": request.session_id
    }
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
        image: your-registry/aicore-api:latest
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