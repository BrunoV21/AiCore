#!/usr/bin/env python3
"""
Example demonstrating asynchronous LLM calls with MCP (Model Control Plane) integration
and multi-turn conversation history.

This script shows how to:
1. Load LLM configuration with MCP settings
2. Initialize an LLM instance with tool calling capabilities
3. Make an async completion request that leverages MCP-connected tools
4. Retrieve the response as message records (conversation history)
5. Make a follow-up call that references the first response, proving
   conversation history is properly preserved across turns
"""

from aicore.config import Config
from aicore.llm import Llm
import asyncio
import json
from pathlib import Path

SYSTEM_PROMPT = (
    "You are a helpful assistant with tool calling capabilities. "
    "Use the tools at your disposal with relevant arguments. "
    "For web searches, suggest three different queries to obtain comprehensive information."
)

async def main():
    """Main async function to demonstrate MCP integration with conversation history."""
    # Load configuration - you can uncomment and modify the path as needed
    # os.environ["CONFIG_PATH"] = "./config/config_example_mcp.yml"
    config = Config.from_yaml()

    if not config.llm.mcp_config:
        raise ValueError(
            "MCP configuration path not found in LLM config. "
            "Please provide a valid mcp_config in your configuration."
        )

    # Print configuration details for transparency
    print("\nLLM Configuration:")
    print(config.llm.model_dump_json(indent=4))

    # Verify MCP config file exists
    mcp_config = Path(config.llm.mcp_config)
    if not mcp_config.exists():
        raise FileNotFoundError(
            f"MCP configuration file not found at: {mcp_config}\n"
            "Please ensure the path is correct and the file exists."
        )

    print("\nMCP Configuration:")
    with open(mcp_config) as f:
        print(json.dumps(json.load(f), indent=4))

    # Initialize LLM with MCP capabilities
    llm = Llm.from_config(config.llm)

    # ── Turn 1: initial request ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("TURN 1: Making initial LLM request with MCP tool calling...")
    print("=" * 60)
    conversation = await llm.acomplete(
        prompt="Search for Elon Musk and tell me what the news from today says about him",
        system_prompt=SYSTEM_PROMPT,
        agent_id="mcp-agent",
        action_id="tool-call",
        as_message_records=True,
    )

    print("\n\nTURN 1 — MESSAGE RECORDS:")
    print(json.dumps(conversation, indent=4, default=str))

    # ── Turn 2: follow-up that depends on Turn 1 ────────────────────
    # Append a follow-up question to the conversation history.
    # This proves the model can reference information from Turn 1.
    conversation.append({
        "role": "user",
        "content": (
            "Based on what you just told me, which of those news stories "
            "do you think will have the biggest long-term impact and why? "
            "Keep it to a short paragraph."
        ),
    })

    print("\n" + "=" * 60)
    print("TURN 2: Sending follow-up (references Turn 1 context)...")
    print("=" * 60)
    follow_up = await llm.acomplete(
        prompt=conversation,
        system_prompt=SYSTEM_PROMPT,
        agent_id="mcp-agent",
        action_id="follow-up",
        as_message_records=True,
    )

    print("\n\nTURN 2 — MESSAGE RECORDS:")
    print(json.dumps(follow_up, indent=4, default=str))

    # ── Full conversation history ────────────────────────────────────
    # Merge Turn 1 context (conversation) with the new records from
    # Turn 2 (follow_up) to get the complete multi-turn history.
    full_history = conversation + follow_up
    print("\n" + "=" * 60)
    print("FULL CONVERSATION HISTORY:")
    print("=" * 60)
    print(json.dumps(full_history, indent=4, default=str))

if __name__ == "__main__":
    asyncio.run(main())
