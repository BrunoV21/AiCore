
# MCP (Multi-Component Platform) Integration

The MCP module enables LLMs to connect to external services via tool calling functionality, allowing seamless integration with various backend services.

## Key Features

- **Server Management**: Connect to multiple MCP servers simultaneously
- **Tool Discovery**: Automatic tool listing from connected servers
- **Unified Interface**: Call tools without knowing which server provides them
- **Transport Flexibility**: Supports multiple connection types:
  - WebSocket (`ws`)
  - Server-Sent Events (`sse`)
  - Standard I/O (`stdio`)
- **Provider Integration**: Works with:
  - OpenAI
  - Gemini
  - Deepseek
  - Anthropic

## Configuration

Configure MCP servers in your LLM config:

```yaml
llm:
  mcp_config_path: "./mcp_config.json"  # Path to MCP configuration
  max_tool_calls_per_response: 3       # Maximum tool calls per LLM response
```

Example MCP config (`mcp_config.json`):

```json
{
  "mcpServers": {
    "search-server": {
      "transport_type": "ws",
      "url": "ws://localhost:8080"
    },
    "data-server": {
      "transport_type": "stdio",
      "command": "python",
      "args": ["data_server.py"]
    },
    "brave-search": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": "BSApeUEgTfLYRikQwW8NAd4Qv8wK2v2"
      }
    }
  }
}
```

## Usage

Basic workflow:

1. Initialize LLM with MCP config
2. The provider will automatically:
   - Connect to configured servers
   - Discover available tools
   - Handle tool calling when needed

### Asynchronous Example

```python
from aicore.config import Config
from aicore.llm import Llm
import asyncio

async def main():
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    
    response = await llm.acomplete(
        "Search for Elon Musk news",
        system_prompt="Use available tools when needed",
        agent_id="mcp-agent"
    )
    print(response)

asyncio.run(main())
```

## Tool Calling Workflow

1. **Initialization**:
   - LLM loads MCP configuration
   - Connects to all configured servers
   - Discovers available tools

2. **Execution**:
   - User makes a request that may require tool usage
   - LLM determines if tools should be called
   - If tools are needed:
     - Calls appropriate tools via MCP
     - Processes tool responses
     - May make additional tool calls if needed
   - Returns final response combining tool outputs

## Error Handling

The MCP module provides robust error handling:

- **Connection Errors**: Automatic retries with exponential backoff
- **Tool Errors**: Detailed error messages including:
  - Which tool failed
  - Error details from the server

## Best Practices

1. **Tool Naming**: Use clear, descriptive names for tools
2. **Error Handling**: Implement comprehensive error handling in your tools
3. **Rate Limiting**: Consider rate limits when making multiple tool calls
4. **Testing**: Test tools thoroughly before production use
5. **Monitoring**: Use the observability features to track tool usage

## Advanced Features

### Custom Transports

You can implement custom transport types by extending the `FastMCPTransport` class.

### Tool Schema Validation

All tools are validated against their schema before being called, ensuring proper input formatting.

### Parallel Tool Execution

The MCP client can handle parallel tool execution when multiple tools are called simultaneously.

For more examples, see the [MCP Examples](../examples/async_llm_call_with_mcp.md) documentation.