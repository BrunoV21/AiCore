"""
### MCP Clients

The `Client` class lets you interact with any MCP server (not just FastMCP ones) from Python code:

You can connect to servers using any supported transport protocol (Stdio, SSE, FastMCP, etc.). If you don't specify a transport, the `Client` class automatically attempts to detect an appropriate one from your connection string or server object.


"""


from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from aicore.llm.mcp.examples.echo import mcp as echo_mcp

async def main():
    async with Client(FastMCPTransport(echo_mcp)) as client:
        # Call a tool
        result = await client.call_tool("echo_tool", {"text": "oky dook"})
        print(result)
        
        # Read a resource
        res = await client.read_resource("echo://bdum")
        print(res)

        # Get a prompt
        prompt = await client.get_prompt("echo", {"text": "okay dude"})
        print(prompt)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
