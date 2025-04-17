
# Chainlit Chat Interface Example

This guide demonstrates how to build a chat interface using Chainlit with AiCore's LLM capabilities.

## Prerequisites

- Python 3.8+
- Chainlit installed (`pip install chainlit`)
- AiCore installed (`pip install aicore`)
- API key for your chosen LLM provider

## Setup

1. First, create a new directory for your Chainlit app:

```bash
mkdir chainlit-app
cd chainlit-app
```

2. Create a configuration file (`config.yml`):

```yaml
llm:
  provider: "openai"  # or any supported provider
  api_key: "your_api_key"
  model: "gpt-4o"     # or your preferred model
  temperature: 0.7
  max_tokens: 1000
```

3. Install required packages:

```bash
pip install chainlit aicore
```

## Implementation

Create an `app.py` file with the following content:

```python
import chainlit as cl
from aicore.llm import Llm
from aicore.config import Config

# Load configuration
config = Config.from_yaml("config.yml")

@cl.on_chat_start
async def start_chat():
    # Initialize LLM when chat starts
    llm = Llm(config=config.llm)
    cl.user_session.set("llm", llm)
    
    # Send welcome message
    await cl.Message(
        content=f"Hello! I'm powered by {config.llm.provider}'s {config.llm.model}. How can I help you?"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    # Get LLM instance from session
    llm = cl.user_session.get("llm")
    
    # Create a message placeholder
    msg = cl.Message(content="")
    await msg.send()
    
    # Stream the response
    response = await llm.acomplete(
        message.content,
        stream=True,
        stream_handler=msg.stream_token
    )
    
    # Update the message with full response
    await msg.update()
```

## Running the Application

Start the Chainlit app with:

```bash
chainlit run app.py -w
```

This will:
1. Start a local server (usually on port 8000)
2. Open the chat interface in your default browser

## Advanced Features

### Adding Memory

To maintain conversation history:

```python
@cl.on_chat_start
async def start_chat():
    llm = Llm(config=config.llm)
    cl.user_session.set("llm", llm)
    cl.user_session.set("history", [])  # Initialize history
    
    await cl.Message(
        content=f"Hello! I remember our conversation. How can I help?"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    llm = cl.user_session.get("llm")
    history = cl.user_session.get("history")
    
    # Add user message to history
    history.append({"role": "user", "content": message.content})
    
    msg = cl.Message(content="")
    await msg.send()
    
    # Include history in the prompt
    response = await llm.acomplete(
        history,
        stream=True,
        stream_handler=msg.stream_token
    )
    
    # Add assistant response to history
    history.append({"role": "assistant", "content": response})
    await msg.update()
```

### File Upload Support

```python
@cl.on_message
async def main(message: cl.Message):
    llm = cl.user_session.get("llm")
    
    # Check for uploaded files
    if message.elements:
        file_content = []
        for element in message.elements:
            if "text" in element.mime:
                with open(element.path, "r") as f:
                    file_content.append(f.read())
        
        prompt = f"{message.content}\n\nFile contents:\n{'\n'.join(file_content)}"
    else:
        prompt = message.content
    
    msg = cl.Message(content="")
    await msg.send()
    
    response = await llm.acomplete(
        prompt,
        stream=True,
        stream_handler=msg.stream_token
    )
    
    await msg.update()
```

### Customizing the UI

Chainlit provides several ways to customize the UI:

```python
@cl.on_chat_start
async def init():
    settings = {
        "model": config.llm.model,
        "temperature": config.llm.temperature,
        "max_tokens": config.llm.max_tokens
    }
    
    await cl.ChatSettings(settings).send()
    
    # Add custom elements
    await cl.Image(
        display="inline",
        path="logo.png",
        size="large"
    ).send()
```

## Deployment Options

### Local Development

```bash
chainlit run app.py -w --port 8000
```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install chainlit aicore

EXPOSE 8000
CMD ["chainlit", "run", "app.py", "--port", "8000"]
```

Build and run:

```bash
docker build -t chainlit-app .
docker run -p 8000:8000 chainlit-app
```

### Cloud Deployment

Chainlit apps can be deployed to any cloud platform that supports Python applications, such as:
- AWS Elastic Beanstalk
- Google App Engine
- Azure App Service
- Render
- Fly.io

## Troubleshooting

1. **API Key Errors**:
   - Ensure your API key is correctly set in `config.yml`
   - Verify the key has proper permissions

2. **Model Not Found**:
   - Check the model name matches your provider's available models
   - Some providers require specific model formats (e.g., "gpt-4" vs "gpt4")

3. **Rate Limiting**:
   - Implement retry logic in your LLM configuration
   - Consider adding rate limiting to your app

4. **Streaming Issues**:
   - Ensure your network allows WebSocket connections
   - Check for firewall restrictions

## Next Steps

- Explore adding [observability](https://docs.aicore.dev/observability/overview) to track usage
- Implement [authentication](https://docs.aicore.dev/quickstart/authentication) for production
- Add [rate limiting](https://docs.aicore.dev/advanced/rate-limiting) to control costs