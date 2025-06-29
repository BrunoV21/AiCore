from typing import Dict, List, Optional, Any, AsyncContextManager, Union
from pydantic import BaseModel, ConfigDict, Field
from pathlib import Path
import asyncio
import time
import json
import os

from fastmcp import Client as FastMCPClient
from fastmcp import FastMCP as FastMCPServer
from fastmcp.client.transports import (
    FastMCPTransport,
    WSTransport, 
    SSETransport,
    StdioTransport,
    StdioServerParameters
)

from aicore.llm.mcp.models import MCPParameters, MCPServerConfig, SSSEParameters, ToolSchema, WSParameters
from aicore.llm.mcp.utils import raise_fast_mcp_error
from aicore.logger import _logger

class ServerConnection(AsyncContextManager):
    """
    A wrapper around FastMCPClient that implements the AsyncContextManager protocol.
    This allows users to access server connections using async with statements.
    """
    def __init__(self, transport: FastMCPTransport):
        self.transport = transport
        self.client = None
        
    async def __aenter__(self):
        self.client = FastMCPClient(self.transport)
        await self.client.__aenter__()
        return self.client
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
            
class ServerManager:
    """
    Manages server connections and provides convenient access to server clients.
    """
    def __init__(self, parent_client: 'MCPClient'):
        self._parent = parent_client
        self._tools_cache = {}  # Cache for mapping tool names to server names
        self._servers_cache :Dict[str, ToolSchema]= {}
        
    def get(self, server_name: str) -> ServerConnection:
        """Get a connection to a specific server by name."""
        if server_name not in self._parent.transports:
            raise KeyError(f"Server '{server_name}' not found in configured servers")
        
        return ServerConnection(self._parent.transports[server_name])
    
    @raise_fast_mcp_error(prefix="mcp-get-tools")
    async def get_tools(self) -> Dict[str, List[ToolSchema]]:
        """Get all tools from all connected servers as a dictionary mapping server names to tool lists."""
        result = {}
        
        for server_name, transport in self._parent.transports.items():
            async with FastMCPClient(transport) as client:
                try:
                    tools = await client.list_tools()
                    result[server_name] = [
                        ToolSchema.from_mcp_tool(tool)
                        for tool in tools
                    ]
                except Exception as e:
                    result[server_name] = [f"Error: {str(e)}"]
                    
        return result
    
    async def get_servers(self) -> Dict[str, str]:
        all_tools =  await self.get_tools()
        for client, servers in all_tools.items():
            for server in servers:
                self._servers_cache[server.name] = client

    @property
    async def tools(self) -> List[ToolSchema]:
        """Get a flat list of all tools from all connected servers."""
        tools_by_server = await self.get_tools()
        all_tools = []
        
        for server_name, tools in tools_by_server.items():
            # Filter out error messages which start with "Error:"
            valid_tools = [tool for tool in tools if not isinstance(tool, str) or not tool.startswith("Error:")]
            all_tools.extend(valid_tools)
            
        return all_tools
    
    @raise_fast_mcp_error(prefix="mcp-call-tool")
    async def call_tool(self, tool_name: str, arguments: Any = None, silent :Optional[bool]=False) -> Any:
        """
        Call a tool by name without specifying which server it belongs to.
        The system will automatically determine which server provides the tool.
        
        Args:
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool
            
        Returns:
            The result of the tool call
            
        Raises:
            ValueError: If the tool is not found on any server
            ValueError: If the tool is found on multiple servers
        """
        # If the tool cache is empty, populate it
        if not self._tools_cache:
            await self.get_servers()
            
        # If the tool is still not in the cache, it's not available
        if tool_name not in self._servers_cache:
            raise ValueError(f"Tool '{tool_name}' not found on any connected server")
        
        server_name = self._servers_cache[tool_name]
        
        # Call the tool on the appropriate server
        _logger.logger.info(f"MCP | Starting call to tool '{tool_name}' on server '{server_name}' with arguments: {arguments}") if not silent else ...
        st = time.perf_counter()
        async with self.get(server_name) as client:
            result = await client.call_tool(tool_name, arguments)
        duration = time.perf_counter() - st
        _logger.logger.info(f"MCP | Finished call to tool '{tool_name}' on server '{server_name}' in {duration:.2f}s") if not silent else ...
        return result

class MCPClient(BaseModel):
    """
    MCP Client that can connect to one or more MCP servers defined in a config file.
    One client can have multiple connections to different servers.
    All interactions should be done within a context manager (with block).
    """
    server_configs: Dict[str, MCPServerConfig] = Field(default_factory=dict)
    transports: Dict[str, FastMCPTransport] = Field(default_factory=dict, exclude=True)
    _is_connected: bool=False
    _needs_update: bool=False
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )
    
    def __init__(self, **data: Any):
        super().__init__(**data)
        # Initialize the server manager
        self._servers = ServerManager(self)
    
    @property
    def servers(self) -> ServerManager:
        """Access the server manager."""
        return self._servers
    
    @classmethod
    def from_config(cls, config: Union[str, Path, Dict[str, str]]) -> "MCPClient":
        """Create an MCPClient instance from a config file."""
        if not isinstance(config, dict):
            if not os.path.exists(config):
                raise FileNotFoundError(f"MCP config file not found: {config}")
            
            with open(config, "r") as f:
                config = json.load(f)
        
        client = cls()
        
        if "mcpServers" in config and isinstance(config["mcpServers"], dict):
            for server_name, server_config in config["mcpServers"].items():
                transport_type = server_config.get("transport_type", "stdio")
                client.server_configs[server_name] = MCPServerConfig(
                    name=server_name,
                    parameters=getattr(MCPParameters, transport_type).value(**server_config),
                    transport_type=transport_type,
                    additional_params=server_config.get("additional_params", {})
                )
        
        return client
    
    def add_server(self, name: str, parameters :Union[FastMCPServer, StdioServerParameters, SSSEParameters, WSParameters], **kwargs) -> None:
        """Add a server configuration manually."""        
        self.server_configs[name] = MCPServerConfig(
            name=name,
            parameters=parameters,
            additional_params=kwargs
        )
        self.transports[name] = self._create_transport(self.server_configs[name])
        self._needs_update = True
    
    @raise_fast_mcp_error(prefix="mcp-connect")
    async def connect(self, server_name: Optional[str] = None) -> None:
        """
        Connect to one or all configured MCP servers.
        
        Args:
            server_name: If provided, connect only to this specific server.
                         If None, connect to all configured servers.
        """
        server_names = [server_name] if server_name else list(self.server_configs.keys())
        for name in server_names:
            if name not in self.server_configs:
                raise KeyError(f"Server '{name}' not found in configured servers")
                
            server_config = self.server_configs[name]
            transport = self._create_transport(server_config)
            self.transports[name] = transport
        self._is_connected = True
    
    def _create_transport(self, server_config: MCPServerConfig) -> FastMCPTransport:
        """Create an appropriate transport based on the server configuration."""
        params = server_config.parameters
        
        if isinstance(params, FastMCPServer):
            return FastMCPTransport(params)
        elif isinstance(params, StdioServerParameters):
            return StdioTransport(
                command=params.command,
                args=params.args,
                env=params.env,
                cwd=params.cwd
            )
        elif isinstance(params, WSParameters):
            return WSTransport(url=params.url)
        elif isinstance(params, SSSEParameters):
            return SSETransport(url=params.url, headers=params.headers)
        else:
            raise ValueError("Unsupported transport type")
            
    async def __aenter__(self) -> "MCPClient":
        """Connect to all servers when entering the context manager."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting the context manager."""
        self.transports.clear()


# Example usage:
async def example_usage():
    # Create from config file
    mcp = MCPClient.from_config_file("mcp_config.json")
    
    # Connect to all servers
    await mcp.connect()
    
    # Option 1: Use the ServerManager to get a specific server
    async with mcp.servers.get("brave-search") as brave_client:
        tools = await brave_client.list_tools()
        print(f"Tools from brave-search: {tools}")
        
        # Call a tool on a specific server
        result = await brave_client.call_tool("brave_web_search", {"query": "python programming"})
        print(f"Search result: {result}")
    
    # Option 2: Get tools by server (dictionary format)
    tools_by_server = await mcp.servers.get_tools()
    print(f"Tools organized by server: {tools_by_server}")
    
    # Option 3: Get flat list of all tools from all servers
    all_tools = await mcp.servers.tools
    print(f"All tools (flat list): {all_tools}")
    
    # Option 4: Call a tool without specifying the server
    try:
        tool_result = await mcp.servers.call_tool("brave_web_search", {"query": "artificial intelligence"})
        print(f"Tool result: {tool_result}")
    except ValueError as e:
        print(f"Error calling tool: {e}")
    
    # Use with context manager
    async with MCPClient.from_config_file("mcp_config.json") as mcp:
        # All servers are automatically connected
        
        # Get flat list of all tools
        all_tools = await mcp.servers.tools
        print(f"All available tools: {all_tools}")
        
        # Call a tool without specifying the server
        if "brave_web_search" in all_tools:
            result = await mcp.servers.call_tool("brave_web_search", {"query": "machine learning"})
            print(f"Search result: {result}")

if __name__ == "__main__":
    asyncio.run(example_usage())