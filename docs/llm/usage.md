
# Usage Tracking and Cost Integration

The LLM module includes comprehensive usage tracking and cost estimation capabilities that work across all supported providers.

## Key Features

- **Token Counting**: Tracks prompt and response tokens for accurate usage metrics
- **Cost Estimation**: Calculates costs based on provider-specific pricing models
- **Caching Support**: Accounts for cached prompt tokens and cache write operations
- **Time-based Pricing**: Supports happy hour pricing variations
- **Dynamic Pricing**: Handles tiered pricing models based on usage volume
- **Multi-model Tracking**: Aggregates usage across different models and providers

## Basic Usage Tracking

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

# Initialize with any provider
config = LlmConfig(
    provider="openai",  # Works with all supported providers
    api_key="your_api_key",
    model="gpt-4o"
)

llm = Llm(config=config)
response = llm.complete("Explain quantum computing")

# Access usage information
print(f"Latest usage: {llm.usage.latest_completion}")
print(f"Total tokens used: {llm.usage.total_tokens}")
print(f"Estimated cost: ${llm.usage.total_cost:.4f}")
```

## Cost Calculation Details

Costs are calculated based on:
- **Input tokens**: Tokens in the prompt/messages
- **Output tokens**: Tokens in the generated response  
- **Cached tokens**: Tokens served from cache (often discounted)
- **Cache writes**: When new prompts are cached

```python
# Get detailed cost breakdown
latest = llm.usage.latest_completion
print(f"Input tokens: {latest.input_tokens}")
print(f"Output tokens: {latest.output_tokens}")
print(f"Cached tokens: {latest.cached_tokens}")
print(f"Cache writes: {latest.cache_writes}")
print(f"Cost: ${latest.cost}")
```

## Advanced Features

### Happy Hour Pricing

```python
# Check if happy hour pricing is active
if llm.usage.latest_completion.happy_hour:
    print("Happy hour pricing applied!")
```

### Cross-Provider Aggregation

```python
# Initialize multiple providers
llm1 = Llm(config_openai)
llm2 = Llm(config_anthropic)

# Aggregate usage across providers
total_cost = llm1.usage.total_cost + llm2.usage.total_cost
print(f"Combined cost: ${total_cost}")
```

## Observability Integration

Usage data is automatically recorded by the observability system:

```python
from aicore.observability.collector import LlmOperationCollector

# Get usage data as Polars DataFrame
df = LlmOperationCollector.polars_from_db()
print(df.select(["provider", "model", "input_tokens", "output_tokens", "cost"]))
```

## Related Documentation

- [Models Metadata](models_metadata.md) - Detailed pricing configurations
- [Observability](../observability/overview.md) - Usage data visualization
- [Base Provider](base_provider.md) - Core tracking implementation