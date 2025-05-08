
# Async LLM Call with MCP Integration Example

This example demonstrates how to make asynchronous LLM calls with MCP (Multi-Component Platform) integration, including tool calling capabilities.

## Prerequisites

- Python 3.8+
- `aicore` package installed
- MCP configuration file (JSON format)
- LLM provider API key (e.g., OpenAI, Deepseek, etc.)

## Configuration

### MCP Configuration (mcp_config.json)

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
    }
  }
}
```

### LLM Configuration (config_example_mcp.yml)

```yaml
llm:
  mcp_config_path: "./mcp_config.json"
  temperature: 0
  max_tokens: 8192
  provider: "deepseek"
  api_key: "your-api-key-here"
  model: "deepseek-chat"
```

## Example Code

```python
from aicore.config import Config
from aicore.llm import Llm
import os
import asyncio
import json

async def main():
    # Load configuration
    config = Config.from_yaml()  # Loads from config_example_mcp.yml by default
    
    # Print configuration details
    print("LLM Configuration:")
    print(json.dumps(config.llm.model_dump(), indent=4))
    print("\nMCP Configuration:")
    with open(config.llm.mcp_config_path) as f:
        print(json.dumps(json.load(f), indent=4))
    
    # Initialize LLM with MCP config
    llm = Llm.from_config(config.llm)
    
    # Make async completion with tool calling
    response = await llm.acomplete(
        "Search for latest AI news about Elon Musk",
        system_prompt="You are a helpful assistant with tool calling capabilities. "
                     "Use available tools when needed and provide comprehensive answers.",
        agent_id="mcp-agent",
        action_id="news-search"
    )
    
    print("\nFINAL RESPONSE:")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## Key Features Demonstrated

1. **Asynchronous LLM Completion**: Uses `acomplete()` for non-blocking API calls
2. **MCP Server Integration**: Automatically connects to configured MCP servers
3. **Tool Calling Workflow**:
   - Automatic tool discovery from connected MCP servers
   - Handling of tool call responses
   - Chaining multiple tool calls when needed
4. **Observability Integration**:
   - Tracks agent_id and action_id for monitoring
   - Records token usage and costs
5. **Configuration Management**:
   - Loads both LLM and MCP configurations
   - Validates required settings

## Expected Output

The example will:
1. Print the loaded configuration
2. Connect to MCP servers and discover available tools
3. Execute the query using available tools
4. Print the final response which may include:
   - Direct LLM-generated content
   - Results from tool calls
   - Combined information from multiple sources

## Troubleshooting

- **Missing MCP Config**: Ensure `mcp_config_path` is set in your LLM config
- **Connection Issues**: Verify MCP servers are running and accessible
- **Tool Calling Errors**: Check tool schemas match expected formats
- **API Errors**: Validate your LLM provider API key and model name

For more details see [MCP Integration Documentation](../llm/mcp.md) and [Base Provider Documentation](../llm/base_provider.md).