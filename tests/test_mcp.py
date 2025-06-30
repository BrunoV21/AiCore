import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aicore.llm.mcp.client import MCPClient, ServerManager, ServerConnection
from aicore.llm.mcp.models import MCPServerConfig, ToolSchema, ToolCallSchema
from aicore.models import FastMcpError
from aicore.llm.mcp.utils import raise_fast_mcp_error
import json
import os
import asyncio

@pytest.fixture
def mock_mcp_config(tmp_path):
    """Fixture providing a mock MCP configuration file."""
    config = {
        "mcpServers": {
            "test-server": {
                "command": "echo",
                "args": ["hello"],
                "transport_type": "stdio"
            },
            "ws-server": {
                "url": "ws://localhost:8080",
                "transport_type": "ws"
            }
        }
    }
    config_path = tmp_path / "mcp_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    return config_path

@pytest.fixture
def mock_tool_schema():
    """Fixture providing a mock ToolSchema instance."""
    return ToolSchema(
        name="test-tool",
        description="Test tool",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )

@pytest.fixture
def mock_mcp_client(mock_mcp_config):
    """Fixture providing a mock MCPClient instance."""
    client = MCPClient.from_config(mock_mcp_config)
    with patch.object(client, "_create_transport", return_value=AsyncMock()):
        yield client

@pytest.mark.asyncio
async def test_mcp_client_from_config(mock_mcp_config):
    """Test creating MCPClient from config file."""
    client = MCPClient.from_config(mock_mcp_config)
    assert isinstance(client, MCPClient)
    assert "test-server" in client.server_configs
    assert "ws-server" in client.server_configs

@pytest.mark.asyncio
async def test_mcp_client_connect(mock_mcp_client):
    """Test connecting MCPClient to servers."""
    await mock_mcp_client.connect()
    assert mock_mcp_client._is_connected
    assert len(mock_mcp_client.transports) == 2

@pytest.mark.asyncio
async def test_mcp_client_context_manager(mock_mcp_config):
    """Test MCPClient as async context manager."""
    with patch("aicore.llm.mcp.client.MCPClient.connect") as mock_connect, \
         patch("aicore.llm.mcp.client.MCPClient.__aexit__") as mock_exit:
        async with MCPClient.from_config(mock_mcp_config) as client:
            assert isinstance(client, MCPClient)
        mock_connect.assert_awaited_once()
        mock_exit.assert_awaited_once()

@pytest.mark.asyncio
async def test_server_manager_get_tools(mock_mcp_client):
    """Test ServerManager.get_tools() method."""
    mock_client = MagicMock()
    mock_client.transports = {"server1": AsyncMock()}
    manager = ServerManager(mock_client)
    
    with patch("aicore.llm.mcp.client.FastMCPClient") as mock_fastmcp:
        mock_fastmcp.return_value.list_tools.return_value = []
        tools = await manager.get_tools()
        assert isinstance(tools, dict)
        assert "server1" in tools

@pytest.mark.asyncio
async def test_server_manager_call_tool(mock_tool_schema, mock_mcp_client):
    """Test ServerManager.call_tool() method."""
    manager = mock_mcp_client.servers
    manager._servers_cache = {"test-tool": "test-server"}
    
    with patch("aicore.llm.mcp.client.FastMCPClient") as mock_fastmcp:
        mock_fastmcp.return_value.call_tool.return_value = "result"
        result = await manager.call_tool("test-tool", {})
        assert result == "result"

@pytest.mark.asyncio
async def test_server_manager_call_tool_not_found(mock_mcp_client):
    """Test ServerManager.call_tool() with non-existent tool."""
    manager = mock_mcp_client.servers
    with pytest.raises(ValueError):
        await manager.call_tool("nonexistent-tool", {})

@pytest.mark.asyncio
async def test_server_connection_context_manager():
    """Test ServerConnection as async context manager."""
    mock_transport = AsyncMock()
    async with ServerConnection(mock_transport) as conn:
        assert isinstance(conn, AsyncMock)
    mock_transport.__aexit__.assert_awaited_once()

def test_tool_schema_from_mcp_tool():
    """Test ToolSchema.from_mcp_tool() method."""
    mock_tool = MagicMock()
    mock_tool.name = "test-tool"
    mock_tool.description = "Test tool"
    mock_tool.inputSchema = {"type": "object"}
    
    tool_schema = ToolSchema.from_mcp_tool(mock_tool)
    assert isinstance(tool_schema, ToolSchema)
    assert tool_schema.name == "test-tool"

def test_tool_call_schema_validation():
    """Test ToolCallSchema validation."""
    tool_call = ToolCallSchema(
        id="123",
        name="test-tool",
        arguments={"param": "value"}
    )
    assert tool_call.name == "test-tool"
    assert tool_call.arguments == {"param": "value"}

@pytest.mark.asyncio
async def test_mcp_error_handling(mock_mcp_client):
    """Test error handling in MCP operations."""
    manager = mock_mcp_client.servers
    manager._servers_cache = {"test-tool": "test-server"}
    
    with patch("aicore.llm.mcp.client.FastMCPClient") as mock_fastmcp, \
         pytest.raises(FastMcpError):
        mock_fastmcp.return_value.call_tool.side_effect = Exception("Test error")
        await manager.call_tool("test-tool", {})

def test_mcp_server_config_validation():
    """Test MCPServerConfig validation."""
    config = MCPServerConfig(
        name="test",
        parameters={"url": "test"},
        transport_type="ws"
    )
    assert config.name == "test"
    assert config.transport_type == "ws"

def test_raise_fast_mcp_error_decorator():
    """Test the raise_fast_mcp_error decorator."""
    @raise_fast_mcp_error(prefix="test")
    def failing_function():
        raise ValueError("Test error")
    
    with pytest.raises(FastMcpError):
        failing_function()

@pytest.mark.asyncio
async def test_mcp_client_add_server():
    """Test adding a server configuration manually."""
    client = MCPClient()
    with patch("aicore.llm.mcp.client.MCPClient._create_transport") as mock_transport:
        mock_transport.return_value = AsyncMock()
        client.add_server("test-server", {"command": "echo", "args": ["hello"]})
        assert "test-server" in client.server_configs
        assert "test-server" in client.transports

@pytest.mark.asyncio
async def test_mcp_client_connect_specific_server(mock_mcp_client):
    """Test connecting to a specific server."""
    await mock_mcp_client.connect("test-server")
    assert "test-server" in mock_mcp_client.transports
    assert len(mock_mcp_client.transports) == 1