"""
aicore.llm.providers.claude_code
=================================
Claude Code provider package for AiCore.

This package exposes two LLM providers built on top of the Claude Agents Python
SDK, plus the shared base class they both inherit from:

Providers
---------
ClaudeCodeLlm (provider name: ``"claude_code"``)
    Runs the Claude Code CLI **locally** on the same machine as AiCore.
    Authentication is handled entirely by the CLI (``claude login``); no API key
    is required.  Use this provider when the CLI is available on the same host.

    Prerequisites::

        npm install -g @anthropic-ai/claude-code   # Node.js 18+ required
        claude login
        pip install core-for-ai

    Minimal config::

        llm:
          provider: "claude_code"
          model: "claude-sonnet-4-5-20250929"

    Optional config fields: ``permission_mode``, ``cwd``, ``max_turns``,
    ``allowed_tools``, ``cli_path``, ``mcp_config``.

RemoteClaudeCodeLlm (provider name: ``"remote_claude_code"``)
    Connects to a running **Claude Code Proxy Server** over HTTP SSE.
    Use this provider when the Claude Code CLI lives on a different machine
    (e.g. a dev box, a server, or a shared service) and AiCore runs in an
    environment that cannot execute the CLI directly.

    Prerequisites::

        pip install core-for-ai               # no CLI needed on the client

    The proxy server must be running and reachable.  Start it with::

        aicore-proxy-server --port 8080 --tunnel none

    Required config fields: ``base_url``, ``api_key`` (the ``CLAUDE_PROXY_TOKEN``
    printed at server startup).

    Minimal config::

        llm:
          provider: "remote_claude_code"
          model: "claude-sonnet-4-5-20250929"
          base_url: "http://your-proxy-host:8080"
          api_key: "your_proxy_token"

    Optional config fields: ``permission_mode``, ``cwd``, ``max_turns``,
    ``allowed_tools``, ``skip_health_check``.

Proxy Server
------------
The proxy server that ``RemoteClaudeCodeLlm`` connects to lives at::

    aicore/scripts/claude_code_proxy_server.py

Run it with::

    aicore-proxy-server [--port PORT] [--host HOST] [--tunnel TUNNEL] ...
    python -m aicore.scripts.claude_code_proxy_server

Install the server-side extras with::

    pip install core-for-ai[claude-server]

Package layout
--------------
::

    claude_code/
    ├── __init__.py   — this file; re-exports all public names
    ├── local.py      — ClaudeCodeBase (shared base), ClaudeCodeLlm
    └── remote.py     — RemoteClaudeCodeLlm

Shared utilities exported from this package
-------------------------------------------
``ClaudeCodeBase``   — abstract base class shared by both providers
``_call_handler``    — async-safe stream handler dispatcher
``_unset_env``       — context manager that temporarily removes env vars
"""

from aicore.llm.providers.claude_code.local import ClaudeCodeBase, ClaudeCodeLlm, _call_handler, _unset_env
from aicore.llm.providers.claude_code.remote import RemoteClaudeCodeLlm

__all__ = [
    "ClaudeCodeBase",
    "ClaudeCodeLlm",
    "RemoteClaudeCodeLlm",
    "_call_handler",
    "_unset_env",
]
