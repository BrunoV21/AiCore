
# Models Metadata System
> Last updated: 2024-06-15

The models metadata system provides standardized information about supported LLM models across all providers, enabling consistent configuration and cost tracking.

## Overview

The metadata system serves as:
- Single source of truth for model capabilities
- Configuration validator for model-specific limits
- Cost calculation reference
- Feature compatibility checker

## Supported Models

| Model ID | Provider | Context Window | Max Tokens | Input Price ($/1M) | Output Price ($/1M) | Cached Price ($/1M) |
|----------|----------|----------------|------------|--------------------|---------------------|---------------------|
| anthropic-claude-3-7-sonnet-latest | Anthropic | 200000 | 64000 | 3.00 | 15.00 | 0.30 |  multimodal |
| anthropic-claude-3-5-sonnet-latest | Anthropic | 200000 | 8192 | 3.00 | 15.00 | 0.30 |  multimodal |
| anthropic-claude-3-5-haiku-latest | Anthropic | 200000 | 8192 | 0.80 | 4.00 | 1.00 | streaming |
| openai-gpt-4.1 | OpenAI | 1047576 | 32768 | 2.00 | 8.00 | 0.50 |  function_calling |
| openai-gpt-4o | OpenAI | 128000 | 64000 | 2.50 | 10.00 | 1.25 |  multimodal, function_calling |
| openai-gpt-4.1-mini | OpenAI | 1047576 | 32768 | 0.40 | 1.60 | 0.10 | streaming |
| openai-gpt-4.1-nano | OpenAI | 1047576 | 32768 | 0.10 | 0.40 | 0.025 | streaming |
| openai-gpt-4o-mini | OpenAI | 1047576 | 16384 | 0.15 | 0.60 | 0.075 | streaming |
| openai-gpt-4.5 | OpenAI | 128000 | 64000 | 75.00 | 150.00 | 37.50 |  multimodal, function_calling |
| openai-o1 | OpenAI | 200000 | 100000 | 15.00 | 60.00 | 7.50 |  function_calling |
| openai-o3-mini | OpenAI | 200000 | 100000 | 1.10 | 4.40 | 0.55 | streaming |
| openai-o3 | OpenAI | 200000 | 100000 | 10.00 | 40.00 | 2.50 |  function_calling |
| openai-o4-mini | OpenAI | 200000 | 100000 | 1.10 | 4.40 | 0.275 | streaming |
| mistral-mistral-large-latest | Mistral | 131072 | 8192 | 2.00 | 6.00 | - | streaming |
| mistral-mistral-small-latest | Mistral | 131072 | 8192 | 0.10 | 0.30 | - | streaming |
| mistral-pixtral-large-latest | Mistral | 131072 | 8192 | 2.00 | 6.00 | - | streaming |
| mistral-codestral-latest | Mistral | 200000 | 8192 | 0.30 | 0.90 | - |  code |
| mistral-ministral-8b-latest | Mistral | 131072 | 8192 | 0.10 | 0.10 | - | streaming |
| mistral-ministral-3b-latest | Mistral | 131072 | 8192 | 0.04 | 0.04 | - | streaming |
| mistral-mistral-embed | Mistral | 8000 | 8192 | 0.10 | 0.00 | - | embeddings |
| mistral-pixtral-12b | Mistral | 131072 | 8192 | 0.15 | 0.15 | - | streaming |
| mistral-mistral-nemo | Mistral | 131072 | 8192 | 0.15 | 0.15 | - | streaming |
| gemini-gemini-2.5-pro-exp-03-25 | Gemini | 1048576 | 64000 | 0.00 | 0.00 | - |  multimodal |
| gemini-gemini-2.0-flash-exp | Gemini | 1048576 | 8192 | 0.00 | 0.00 | - | streaming |
| gemini-gemini-2.0-flash-thinking-exp-01-21 | Gemini | 1048576 | 65536 | 0.00 | 0.00 | - |  thinking |
| gemini-gemini-2.0-flash | Gemini | 1048576 | 8192 | 0.10 | 0.40 | - | streaming |
| gemini-gemini-2.0-flash-lite | Gemini | 1048576 | 8192 | 0.075 | 0.30 | - | streaming |
| gemini-gemini-2.5-pro-preview-03-25 | Gemini | 1048576 | 64000 | 1.25 | 10.00 | - |  multimodal |
| groq-meta-llama/llama-4-scout-17b-16e-instruct | Groq | 131072 | 8192 | 0.11 | 0.34 | - | streaming |
| groq-meta-llama/llama-4-maverick-17b-128e-instruct | Groq | 131072 | 8192 | 0.50 | 0.77 | - | streaming |
| groq-deepseek-r1-distill-llama-70b | Groq | 128000 | 8192 | 0.75 | 0.99 | - | streaming |
| groq-deepseek-r1-distill-qwen-32b | Groq | 128000 | 16384 | 0.69 | 0.69 | - | streaming |
| groq-qwen-2.5-32b | Groq | 128000 | 16384 | 0.79 | 0.79 | - | streaming |
| groq-qwen-2.5-coder-32b | Groq | 128000 | 16384 | 0.79 | 0.79 | - |  code |
| groq-qwen-qwq-32b | Groq | 128000 | 16384 | 0.29 | 0.39 | - | streaming |
| groq-mistral-saba-24b | Groq | 200000 | 16384 | 0.79 | 0.79 | - | streaming |
| deepseek-deepseek-reasoner | Deepseek | 65536 | 8192 | 0.55 | 2.10 | 0.14 |  thinking |
| deepseek-deepseek-chat | Deepseek | 65536 | 8192 | 0.27 | 1.10 | 0.07 | streaming |
| grok-3-beta | Groq | 131072 | 8192 | 3.00 | 15.00 | - | streaming |
| grok-3-mini-beta | Groq | 131072 | 8192 | 0.20 | 0.50 | - | streaming |

> Note: Prices are per million tokens. "-" indicates no caching available. Feature abbreviations: streaming (real-time responses), multimodal (image/audio support), function_calling (tool use), thinking (reasoning steps), code (code generation).

## Accessing Metadata

```python
from aicore.models_metadata import METADATA

# Get metadata for a specific model
gpt4_metadata = METADATA["openai-gpt-4o"]

# List all available models
all_models = list(METADATA.keys())
```

## Metadata Structure

Each model entry contains:

```python
class ModelMetaData(BaseModel):
    context_window: int          # Maximum context size in tokens
    max_tokens: int              # Maximum generation tokens
    pricing: Optional[PricingConfig] = None
```

## Pricing Configuration

The pricing system supports:

```python
class PricingConfig(BaseModel):
    input: float                 # $ per 1M input tokens
    output: float                # $ per 1M output tokens
    cached: float = 0            # Discount for cached prompts
    cache_write: float = 0       # Cost for caching prompts
    happy_hour: Optional[Dict[str, Tuple[float, float]]] = None  # Discount periods i.e. Deepseek
    dynamic: Optional[DynamicPricing] = None # Dynamic pricing based on tokens consumed i.e. Gemini
```

### Example Usage

```python
# Calculate request cost
model_data = METADATA["anthropic-claude-3-7-sonnet"]
cost = model_data.pricing.calculate_cost(
    prompt_tokens=1500,
    response_tokens=800
)
```

## Best Practices

1. **Always check model limits**:
   ```python
   if len(prompt) > METADATA[model].context_window:
       raise ValueError("Prompt too long")
   ```

2. **Use metadata for cost estimation**:
   ```python
   budget = 10.00
   estimated_cost = METADATA[model].estimate_cost(prompt)
   if estimated_cost > budget:
       # Choose cheaper model
   ```

See also:
- [Base Provider Documentation](./base_provider.md)
- [Usage Tracking](./usage.md)
- [Configuration System](../config/llmconfig.md)