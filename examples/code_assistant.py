#!/usr/bin/env python3
"""
mcp_config.json
{
  "mcpServers": {
    "codetide": {
      "command": "uvx",
      "args": [
        "--from",
        "codetide",
        "codetide-mcp-server"
      ],
      "env": {
        "CODETIDE_WORKSPACE": "./"
      }
    }
  }
}
"""

from aicore.config import Config
from aicore.llm import Llm
from pathlib import Path
import asyncio
import json

async def main():
    """Main async function to demonstrate MCP integration."""
    # Load configuration - you can uncomment and modify the path as needed
    # os.environ["CONFIG_PATH"] = "./config/config_example_mcp.yml"
    config = Config.from_yaml()
    
    if not config.llm.mcp_config_path:
        raise ValueError(
            "MCP configuration path not found in LLM config. "
            "Please provide a valid mcp_config_path in your configuration."
        )

    # Print configuration details for transparency
    print("\nLLM Configuration:")
    print(config.llm.model_dump_json(indent=4))
    
    # Verify MCP config file exists
    mcp_config_path = Path(config.llm.mcp_config_path)
    if not mcp_config_path.exists():
        raise FileNotFoundError(
            f"MCP configuration file not found at: {mcp_config_path}\n"
            "Please ensure the path is correct and the file exists."
        )

    print("\nMCP Configuration:")
    with open(mcp_config_path) as f:
        print(json.dumps(json.load(f), indent=4))

    # Initialize LLM with MCP capabilities
    llm = Llm.from_config(config.llm)

    # Make async completion request with tool calling
    print("\nMaking LLM request with MCP tool calling...")
    response = await llm.acomplete(
        prompt="Summarize the contents of the AiCore README file",
        agent_id="mcp-agent",
        action_id="tool-call"
    )

if __name__ == "__main__":
    asyncio.run(main())
