
# Models Metadata System

The models metadata system provides standardized information about supported LLM models across all providers, enabling consistent configuration and cost tracking.

## Overview

The metadata system serves as:
- Single source of truth for model capabilities
- Configuration validator for model-specific limits
- Cost calculation reference
- Feature compatibility checker

## Accessing Metadata

```python
from aicore.models_metadata import METADATA

# Get metadata for a specific model
gpt4_metadata = METADATA["openai-gpt-4"]

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
    features: List[str]          # Supported features
    provider: str                # Provider name
    model_family: str            # Model family/version
```

## Pricing Configuration

The pricing system supports:

```python
class PricingConfig(BaseModel):
    input: float                 # $ per 1M input tokens
    output: float                # $ per 1M output tokens
    cached: float = 0            # Discount for cached prompts
    cache_write: float = 0       # Cost for caching prompts
    happy_hour: Optional[Dict[str, Tuple[float, float]]] = None  # Discount periods
```

### Example Usage

```python
# Calculate request cost
model_data = METADATA["anthropic-claude-3-sonnet"]
cost = model_data.pricing.calculate_cost(
    prompt_tokens=1500,
    response_tokens=800
)
```

## Model Features

Common feature flags include:
- `streaming`: Supports streaming responses
- `multimodal`: Accepts image/audio inputs  
- `function_calling`: Supports tool use
- `json_mode`: Constrained JSON output
- `thinking`: Supports reasoning steps

```python
# Check feature support
if "multimodal" in METADATA["openai-gpt-4o"].features:
    # Handle image inputs
```

## Provider Integration

Providers automatically register their models:

```python
# Example provider registration
METADATA.register(
    "groq-llama3-70b",
    context_window=8192,
    max_tokens=4096,
    pricing=PricingConfig(input=0.5, output=0.75),
    features=["streaming", "json_mode"]
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

3. **Verify feature compatibility**:
   ```python
   if needs_json and "json_mode" not in METADATA[model].features:
       # Fallback to different approach
   ```

See also:
- [Base Provider Documentation](./base_provider.md)
- [Usage Tracking](./usage.md)
- [Configuration System](../config/llmconfig.md)