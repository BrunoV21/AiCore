
from fastmcp.client.transports import StdioServerParameters
from fastmcp import FastMCP as FastMCPServer
from mcp.types import Tool

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, RootModel
from enum import Enum

class WSParameters(BaseModel):
    url: str

class SSSEParameters(BaseModel):
    url: str
    headers: dict[str, Any] | None = None
    timeout: float = 5
    sse_read_timeout: float = 60 * 5

class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server connection."""
    name: str
    parameters :Union[FastMCPServer, StdioServerParameters, SSSEParameters, WSParameters]
    transport_type: Literal["stdio", "sse", "ws"] = "stdio"  # Can be "fastmcp", "stdio", "ws", "sse", or None for stdio
    additional_params: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class MCPParameters(Enum):
    ws :WSParameters=WSParameters
    sse :SSSEParameters=SSSEParameters
    stdio :StdioServerParameters=StdioServerParameters

class PropertiesSchema(BaseModel):

    model_config = ConfigDict(
        extra="allow",
    )

class InputSchema(BaseModel):
    type :str
    properties :PropertiesSchema
    required :List[str]

    model_config = ConfigDict(
        extra="allow",
    )

class ToolSchema(BaseModel):
    name :str
    description :str
    input_schema :InputSchema

    @classmethod
    def from_mcp_tool(cls, tool :Tool)->"ToolSchema":
        return cls(
            name=tool.name,
            description=tool.description,
            input_schema=InputSchema(**tool.inputSchema)
        )

class ToolCallSchema(BaseModel):
    type :str="function"
    id :str
    name :str
    arguments :Union[str, Dict]
    _raw :Optional[Any]=None
    

    """
    [
        Tool(
            name='brave_web_search',
            description='Performs a web search using the Brave Search API, ideal for general queries, news, articles, and online content.
                Use this for broad information gathering, recent events, or when you need diverse web sources.
                Supports pagination, content filtering, and freshness controls. Maximum 20 results per request, with offset for pagination.',
            inputSchema={
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'Search query (max 400 chars, 50 words)'
                    },
                    'count': {
                        'type': 'number',
                        'description': 'Number of results (1-20, default 10)', 'default': 10
                    },
                    'offset': {
                        'type': 'number',
                        'description': 'Pagination offset (max 9, default 0)',
                        'default': 0
                    }
                }, 
                'required': ['query']
            }
        )
    ]
    """

    """
    ### Anthropic
    {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "input_schema": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "The city and state, e.g. San Francisco, CA"
            }
          },
          "required": [
            "location"
          ]
        }
      }
    ### Deepseek
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather of an location, the user shoud supply a location first",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    }
                },
                "required": ["location"]
            },
        }
    }
    #### OpenAI
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get current temperature for a given location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City and country e.g. Bogotá, Colombia"
                }
            },
            "required": [
                "location"
            ],
            "additionalProperties": False
        }
    }
    """

class ToolCalls(RootModel):
    root: List[ToolCallSchema] = []