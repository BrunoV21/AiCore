
# Retry Mechanism

The LLM module implements a robust retry mechanism to handle transient failures when interacting with LLM providers. This system ensures reliable operation even when facing temporary network issues or API rate limits.

## Key Features

- **Exponential Backoff**: Automatically increases delay between retry attempts (default: 1s, 2s, 4s, 8s)
- **Error Classification**: Differentiates between retryable and non-retryable errors
- **Configurable Attempts**: Maximum retry attempts can be configured (default: 3)
- **Circuit Breaker**: Prevents cascading failures by temporarily disabling calls to failing providers
- **Jitter**: Adds random variation to retry delays to prevent thundering herd problems

## Implementation

The retry mechanism is implemented via the `@retry_on_failure` decorator from `aicore.utils`:

```python
from aicore.utils import retry_on_failure

@retry_on_failure(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    backoff_factor=2.0
)
async def complete(self, prompt: str) -> str:
    """LLM completion with automatic retries"""
    response = await self._client.acreate(prompt)
    return response
```

## Configuration Options

Retry behavior can be configured either through environment variables or directly in code:

### Environment Variables
```bash
# Maximum retry attempts
export LLM_MAX_RETRIES=5

# Initial retry delay in seconds
export LLM_RETRY_INITIAL_DELAY=1.5

# Maximum delay between retries
export LLM_RETRY_MAX_DELAY=15.0

# Backoff multiplier factor
export LLM_RETRY_BACKOFF_FACTOR=2.0
```

### Programmatic Configuration
```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="openai",
    api_key="your_api_key",
    model="gpt-4",
    retry_settings={
        "max_attempts": 5,
        "initial_delay": 1.5,
        "max_delay": 15.0,
        "backoff_factor": 2.0
    }
)
```

## Error Handling

### Retryable Errors (automatic retry)
- Network timeouts (408)
- Rate limit errors (429)
- Server errors (5xx)
- Temporary unavailability (503)
- Connection errors

### Non-Retryable Errors (fail immediately)
- Authentication failures (401)
- Invalid requests (400, 404)
- Permission errors (403)
- Model not found errors
- Validation errors

## Customizing Retry Logic

You can customize the retry behavior by subclassing the base provider:

```python
from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.utils import retry_on_failure

class CustomProvider(LlmBaseProvider):
    @retry_on_failure(
        max_attempts=5,
        retry_on=(RateLimitError, TimeoutError),
        give_up_on=(AuthenticationError,)
    )
    async def acomplete(self, prompt: str) -> str:
        # Custom implementation with specialized retry logic
        pass
```

## Monitoring Retries

Retry attempts are tracked in the observability system and can be monitored:

```python
from aicore.observability.collector import LlmOperationCollector

# Get retry statistics
df = LlmOperationCollector.polars_from_db()
retry_stats = df.group_by("provider").agg(
    pl.col("retry_count").mean().alias("avg_retries"),
    pl.col("retry_count").max().alias("max_retries")
)
```

For more advanced monitoring, see the [Observability Dashboard](../observability/dashboard.md).