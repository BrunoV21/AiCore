
# Gemini Provider

The Gemini provider implements support for Google's Gemini models through the Google Generative AI API.

## Supported Models

```python
from aicore.models_metadata import METADATA

# List available Gemini models
gemini_models = [model for model in METADATA if model.startswith("gemini-")]
print(gemini_models)
```

## Key Features

- Supports both text and multimodal inputs
- Free tier available for testing
- Optimized token counting implementation
- Streaming support
- Usage tracking and cost estimation
- Safety settings configuration

## Configuration

### Python Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="gemini",
    api_key="your_api_key",
    model="gemini-1.5-pro",
    temperature=0.7,
    safety_settings={
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
        "HARM_CATEGORY_HARASSMENT": "BLOCK_ONLY_HIGH"
    }
)
```

### YAML Configuration

```yaml
provider: gemini
api_key: "your_api_key"
model: "gemini-1.5-pro"
temperature: 0.7
safety_settings:
  HARM_CATEGORY_DANGEROUS_CONTENT: "BLOCK_NONE"
  HARM_CATEGORY_HARASSMENT: "BLOCK_ONLY_HIGH"
```

## Usage Examples

### Basic Completion

```python
from aicore.llm import Llm

llm = Llm(config=config)
response = llm.complete("Explain quantum computing in simple terms")
print(response)
```

### Multimodal Input

```python
from aicore.llm.models import MultimodalContent

content = MultimodalContent(
    text="What's in this image?",
    images=["path/to/image.jpg"]
)

response = llm.complete(content)
```

### Streaming

```python
stream = llm.stream("Write a poem about AI")
for chunk in stream:
    print(chunk, end="", flush=True)
```

## Advanced Features

### Safety Settings

Gemini provides configurable safety settings for content moderation. You can adjust these per request:

```python
response = llm.complete(
    "Controversial topic question",
    safety_settings={
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE"
    }
)
```

### Token Counting

```python
usage = llm.get_last_usage()
print(f"Input tokens: {usage.input_tokens}")
print(f"Output tokens: {usage.output_tokens}")
```

## Troubleshooting

- **Authentication Errors**: Ensure your API key is valid and has access to the Gemini API
- **Model Not Found**: Verify the model name matches exactly what's in `METADATA`
- **Safety Blocks**: Adjust safety settings if getting blocked for harmless content