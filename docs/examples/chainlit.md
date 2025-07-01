# Chainlit Chat Interface Example

This guide demonstrates how to build a chat interface using Chainlit with AiCore's LLM capabilities, including advanced features like reasoning integration and dynamic chat profiles.

## Prerequisites

- Python 3.8+
- Chainlit installed (`pip install chainlit`)
- AiCore installed (`pip install core-for-ai`)
- API keys for supported LLM providers

## Chat Profiles

The example provides two default chat profiles:

1. **Reasoner4All** - Uses Mistral with a Groq-powered reasoner
2. **OpenAi** - Uses OpenAI with a Groq-powered reasoner

You can customize these in the `DEFAULT_LLM_CONFIG` dictionary in `app.py`.

## Setup

1. First, create a new directory for your Chainlit app:

```bash
mkdir chainlit-app
cd chainlit-app
```

2. Create a `.env` file with API keys:

```env
OPENAI_API_KEY=your_openai_key
MISTRAL_API_KEY=your_mistral_key
GROQ_API_KEY=your_groq_key
```

3. Install required packages:

```bash
pip install chainlit core-for-ai
```

## Implementation

Create an `app.py` file with the following content:

```python
[See full implementation in examples/chainlit/app/app.py]
```

## Running the Application

Start the Chainlit app with:

```bash
chainlit run app.py -w
```

## Key Features

1. **Dynamic Chat Profiles** - Switch between different LLM configurations
2. **Reasoning Integration** - Built-in reasoning capabilities via secondary LLM
3. **API Key Validation** - On-demand key validation
4. **Conversation History** - Automatic message trimming based on token count
5. **Observability** - Built-in logging and monitoring

## Customization

To customize the implementation:

1. Edit `DEFAULT_LLM_CONFIG` in `app.py` to change default models
2. Modify `PROFILES_SETTINGS` in `settings.py` to customize chat profiles
3. Update `MODELS_PROVIDERS_MAP` in `utils.py` to add new model-provider mappings

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

## Troubleshooting

1. **API Key Errors**:
   - Ensure your API keys are correctly set in `.env`
   - Verify the keys have proper permissions

2. **Model Not Found**:
   - Check the model name matches your provider's available models
   - Some providers require specific model formats

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