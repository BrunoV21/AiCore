
# Base LLM Provider Interface

The `LlmBaseProvider` class serves as the abstract base class for all LLM provider implementations in AiCore, providing a unified interface and common functionality.

## Core Features

- **Provider Agnostic Design**: Standardized interface across all supported LLM providers
- **Dual Mode Support**: Both synchronous (`complete`) and asynchronous (`acomplete`) methods
- **Streaming Support**: Built-in handling for streaming responses
- **Usage Tracking**: Automatic token counting and cost estimation
- **Observability Integration**: Built-in metrics collection for monitoring
- **Error Handling**: Standardized retry mechanism for failed requests

## Interface Methods

### Core Completion Methods

```python
class LlmBaseProvider(ABC):
    @abstractmethod
    def complete(self, 
                prompt: str,
                system_prompt: Optional[str] = None,
                prefix_prompt: Optional[str] = None,
                img_path: Optional[str] = None,
                json_output: bool = False,
                stream: bool = False) -> Union[str, Dict]:
        """Synchronous completion with standard parameters"""
        
    @abstractmethod
    async def acomplete(self,
                      prompt: str,
                      system_prompt: Optional[str] = None,
                      prefix_prompt: Optional[str] = None,
                      img_path: Optional[str] = None,
                      json_output: bool = False,
                      stream: bool = False) -> Union[str, Dict]:
        """Asynchronous completion with standard parameters"""
```

### Additional Methods

```python
    def get_usage(self) -> LlmUsage:
        """Returns usage statistics for the provider instance"""
        
    def get_config(self) -> LlmConfig:
        """Returns the current configuration"""
        
    @classmethod
    def from_config(cls, config: LlmConfig) -> 'LlmBaseProvider':
        """Factory method to create provider from config"""
```

## Configuration

Providers are configured via the `LlmConfig` class:

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="openai",  # Provider name matching implementation
    api_key="your_api_key",
    model="gpt-4",
    temperature=0.7,
    max_tokens=1000,
    timeout=30.0
)
```

## Implementing a New Provider

To create a new provider implementation:

1. Inherit from `LlmBaseProvider`
2. Implement required abstract methods
3. Handle provider-specific API communication
4. Normalize responses to standard format

### Example Provider Skeleton

```python
from aicore.llm.providers.base_provider import LlmBaseProvider

class CustomProvider(LlmBaseProvider):
    def __init__(self, config: LlmConfig):
        super().__init__(config)
        # Initialize provider-specific client
        
    def complete(self, prompt, **kwargs):
        # Implement synchronous completion
        pass
        
    async def acomplete(self, prompt, **kwargs):
        # Implement asynchronous completion
        pass
```

## Response Format

All providers should return responses in a standardized format:

```python
{
    "content": "The generated response text",
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300
    },
    "cost": 0.0035,  # Calculated cost in USD
    "model": "provider-model-name"
}
```

## Error Handling

The base provider includes standardized error handling for:
- Rate limits (automatic retry with backoff)
- Invalid requests
- Authentication failures
- Service unavailable errors

See [retry mechanism documentation](./retry.md) for details.

## Observability Integration

All providers automatically track:
- Request/response timing
- Token usage
- Cost calculations
- Error rates

Metrics are available through the [observability system](../observability/overview.md).