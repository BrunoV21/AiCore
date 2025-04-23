"""
include support to load mcp clients from config in config
see exampe here https://mcpservers.org/official

### 

### Claude Desktop like config:
npm install -g agentql-mcp 
+ to claude_desktop_config.json
{
  "mcpServers": {
    "agentql": {
      "command": "npx",
      "args": ["-y", "agentql-mcp"],
      "env": {
        "AGENTQL_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}

---
{
  "mcpServers": {
    "@21st-dev/magic": {
      "command": "npx",
      "args": ["-y", "@21st-dev/magic@latest", "API_KEY=\"your-api-key\""]
    }
  }
}

mcp_config_json -> load from default location on root or from

meed to cover loading of all mcp servers + descriptions and incorporate them into plan the llm can decide which one to choose
"""