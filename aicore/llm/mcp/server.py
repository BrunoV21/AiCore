from fastmcp import FastMCP
"""
https://github.com/jlowin/fastmcp

## Core Concepts

These are the building blocks for creating MCP servers, using the familiar decorator-based approach.

### The `FastMCP` Server

The central object representing your MCP application. It handles connections, protocol details, and routing.

### Tools

Tools allow LLMs to perform actions by executing your Python functions. They are ideal for tasks that involve computation, external API calls, or side effects.

Decorate synchronous or asynchronous functions with `@mcp.tool()`. FastMCP automatically generates the necessary MCP schema based on type hints and docstrings. Pydantic models can be used for complex inputs.

### Resources

Resources expose data to LLMs. They should primarily provide information without significant computation or side effects (like GET requests).

Decorate functions with `@mcp.resource("your://uri")`. Use curly braces `{}` in the URI to define dynamic resources (templates) where parts of the URI become function parameters.

### Prompts

Prompts define reusable templates or interaction patterns for the LLM. They help guide the LLM on how to use your server's capabilities effectively.

Decorate functions with `@mcp.prompt()`. The function should return the desired prompt content, which can be a simple string, a `Message` object (like `UserMessage` or `AssistantMessage`), or a list of these.

### Context

Gain access to MCP server capabilities *within* your tool or resource functions by adding a parameter type-hinted with `fastmcp.Context`.

The `Context` object provides:
*   Logging: `ctx.debug()`, `ctx.info()`, `ctx.warning()`, `ctx.error()`
*   Progress Reporting: `ctx.report_progress(current, total)`
*   Resource Access: `await ctx.read_resource(uri)`
*   Request Info: `ctx.request_id`, `ctx.client_id`
*   Sampling (Advanced): `await ctx.sample(...)` to ask the connected LLM client for completions.

### Images

Easily handle image input and output using the `fastmcp.Image` helper class.
FastMCP handles the conversion to/from the base64-encoded format required by the MCP protocol.
"""

# Create a named server
mcp = FastMCP("My App")

# Specify dependencies needed when deployed via `fastmcp install`
mcp = FastMCP("My App", dependencies=["pandas", "numpy"])