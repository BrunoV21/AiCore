#!/usr/bin/env python3
"""
Example demonstrating asynchronous LLM calls with MCP (Model Control Plane) integration.

This script shows how to:
1. Load LLM configuration with MCP settings
2. Initialize an LLM instance with tool calling capabilities
3. Make an async completion request that leverages MCP-connected tools
4. Handle and display the response with tool call information
"""

from aicore.config import Config
from aicore.llm import Llm
import asyncio
import json
from pathlib import Path

async def main():
    """Main async function to demonstrate MCP integration."""
    try:
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
            prompt="Search for Elon Musk and tell me what the news from today says about him",
            system_prompt=(
                "You are a helpful assistant with tool calling capabilities. "
                "Use the tools at your disposal with relevant arguments. "
                "For web searches, suggest three different queries to obtain comprehensive information."
            ),
            agent_id="mcp-agent",
            action_id="tool-call"
        )

        # Display the final response
        print("\n\nFINAL RESPONSE:")
        if isinstance(response, dict):
            print(json.dumps(response, indent=4))
        else:
            print(response)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
