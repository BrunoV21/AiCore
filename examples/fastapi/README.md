# LLM Service API

A modular FastAPI application that provides API and WebSocket endpoints for interacting with Large Language Models (LLMs).

## Overview

This project implements a scalable microservice architecture for deploying and interacting with LLMs. It includes features such as:

* REST API for synchronous LLM interactions
* WebSocket support for streaming LLM responses
* Authentication using JWT tokens
* Session management with unique identifiers
* Customizable LLM configurations

## Project Structure

```
project/
├── main.py               # Main application entry point
├── config.py             # Configuration settings
├── models/               # Pydantic models
│   ├── __init__.py
│   └── schemas.py        # Data schemas/models
├── auth/                 # Authentication related code
│   ├── __init__.py
│   ├── dependencies.py   # Auth dependencies
│   └── utils.py          # Auth utility functions
├── api/                  # API endpoints
│   ├── __init__.py
│   ├── routes.py         # API route definitions
│   └── websockets.py     # WebSocket handlers
├── services/             # Business logic
│   ├── __init__.py
│   └── llm_service.py    # LLM service
└── requirements.txt      # Project dependencies
```

## Installation

1. Clone the repository
2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The application can be configured using environment variables:
* `SECRET_KEY`: Secret key for JWT token generation
* `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT token expiration time

## Usage

### Running the server

```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

### API Endpoints

#### Authentication

```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=testuser&password=password
```

#### Set Custom LLM Configuration

```http
POST /set-llm
Content-Type: application/json

{
  "model_name": "gpt-4",
  "temperature": 0.8,
  "max_tokens": 2000,
  "top_p": 0.95
}
```

Returns a session ID to use in subsequent requests.

#### Chat Request

```http
POST /chat
Content-Type: application/json

{
  "session_id": "your-session-id",
  "message": "Hello, how can you help me today?"
}
```

### WebSocket

Connect to a WebSocket at:

```
ws://localhost:8000/ws/{session_id}
```

Send messages as text strings. The history of messages is maintained for context in the conversation.

Example:
```
"Hello, how can you help me today?"
```

The response will be streamed as chunks in JSON format:

```json
{"chunk": "I'm"}
{"chunk": " an"}
{"chunk": " AI"}
{"chunk": " assistant"}
...
```

## Development

This project is built using the `aicore` package, which provides the core LLM functionality. The implementation includes:

- Session management with `ULID` for unique session identifiers
- Conversation history tracking 
- Streaming responses with WebSockets
- Special token handling

### Adding New Features

1. Create new schemas in `models/schemas.py`
2. Add new routes in `api/routes.py` or `api/websockets.py`
3. Implement business logic in `services/`