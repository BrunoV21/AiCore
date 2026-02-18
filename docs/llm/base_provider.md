
# Base LLM Provider Interface

The `LlmBaseProvider` class serves as the abstract base class for all LLM provider implementations in AiCore, providing a unified interface and common functionality.

## Core Features

- **Provider Agnostic Design**: Standardized interface across all supported LLM providers
- **Dual Mode Support**: Both synchronous (`complete`) and asynchronous (`acomplete`) methods
- **Streaming Support**: Built-in handling for streaming responses
- **Usage Tracking**: Automatic token counting and cost estimation
- **Observability Integration**: Built-in metrics collection for monitoring
- **MCP Integration**: Built-in support for connecting to MCP servers via tool calling
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
    @property
    def usage(self) -> LlmUsage:
        """Returns usage statistics for the provider instance"""
        
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
    mcp_config="path/to/mcp_config.json",  # Optional MCP configuration
    timeout=30.0
)
```

## MCP Integration

The base provider includes built-in support for connecting to MCP (Multi-Component Platform) servers via tool calling. Key features:

- Automatic tool discovery from connected MCP servers
- Unified interface for calling tools across multiple servers
- Configurable maximum tool calls per response
- Support for multiple transport types (WebSocket, SSE, Stdio)

See [MCP Integration Documentation](./mcp.md) for full details.

## Implementing a New Provider

To create a new provider implementation:

1. Inherit from `LlmBaseProvider`
2. Implement required abstract methods
3. Handle provider-specific API communication
4. Normalize responses to standard format
5. Implement tool calling support if applicable

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

## Error Handling

The base provider includes standardized error handling for:
- Rate limits (automatic retry with backoff)
- Invalid requests
- Authentication failures
- MCP server connection failures
- Service unavailable errors

See [retry mechanism documentation](./retry.md) for details.

## Observability Integration

All providers automatically track:
- Request/response timing
- Token usage
- Cost calculations
- Error rates
- Tool calling metrics (when using MCP)

Metrics are available through the [observability system](../observability/overview.md).