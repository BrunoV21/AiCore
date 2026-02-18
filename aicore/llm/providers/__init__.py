"""
aicore.llm.providers
=====================
Registry of all AiCore LLM provider classes.

Each provider implements the ``LlmBaseProvider`` interface and can be
instantiated via ``Llm.from_config(LlmConfig(provider=..., ...))`` or
directly through the provider class.

Available providers
-------------------

Standard API providers
~~~~~~~~~~~~~~~~~~~~~~
These providers require an API key (``api_key`` field in ``LlmConfig``).

=================  ============================================================
Provider name      Class
=================  ============================================================
``"anthropic"``    ``AnthropicLlm``     — Anthropic Claude API
``"openai"``       ``OpenAiLlm``        — OpenAI / Azure OpenAI
``"gemini"``       ``GeminiLlm``        — Google Gemini
``"groq"``         ``GroqLlm``          — Groq
``"mistral"``      ``MistralLlm``       — Mistral AI
``"nvidia"``       ``NvidiaLlm``        — NVIDIA NIM
``"openrouter"``   ``OpenRouterLlm``    — OpenRouter
``"grok"``         ``GrokLlm``          — xAI Grok
``"deepseek"``     ``DeepSeekLlm``      — DeepSeek
``"zai"``          ``ZaiLlm``           — ZhipuAI / Z.AI
=================  ============================================================

Claude Code providers
~~~~~~~~~~~~~~~~~~~~~
These providers use your **Claude subscription** via the Claude Agents Python
SDK.  No Anthropic API key is needed.

``"claude_code"``  →  ``ClaudeCodeLlm``
    Runs the Claude Code CLI **locally** on the same machine.

    Prerequisites::

        npm install -g @anthropic-ai/claude-code
        claude login

    Minimal config::

        llm:
          provider: "claude_code"
          model: "claude-sonnet-4-5-20250929"

    Optional fields: ``permission_mode``, ``cwd``, ``max_turns``,
    ``allowed_tools``, ``cli_path``, ``mcp_config``.

``"remote_claude_code"``  →  ``RemoteClaudeCodeLlm``
    Connects to a running ``aicore-proxy-server`` over HTTP SSE.  Use this
    when the CLI lives on a different machine or in a shared environment.

    Prerequisites (client-side)::

        pip install core-for-ai

    Start the proxy server (server-side)::

        pip install core-for-ai[claude-server]
        aicore-proxy-server --port 8080 --tunnel none

    Required config fields: ``base_url``, ``api_key`` (the
    ``CLAUDE_PROXY_TOKEN`` printed at server startup).

    Minimal config::

        llm:
          provider: "remote_claude_code"
          model: "claude-sonnet-4-5-20250929"
          base_url: "http://your-proxy-host:8080"
          api_key: "your_proxy_token"

    Optional fields: ``permission_mode``, ``cwd``, ``max_turns``,
    ``allowed_tools``, ``skip_health_check``.

See also
--------
- ``aicore.llm.providers.claude_code``  — local + remote provider package
- ``aicore.scripts.claude_code_proxy_server``  — the proxy server
- ``config/config_example_claude_code.yml``  — local provider config example
- ``config/config_example_remote_claude_code.yml``  — remote provider config
"""

from aicore.llm.providers.gemini import GeminiLlm
from aicore.llm.providers.groq import GroqLlm
from aicore.llm.providers.mistral import MistralLlm
from aicore.llm.providers.nvidia import NvidiaLlm
from aicore.llm.providers.anthropic import AnthropicLlm
from aicore.llm.providers.openai import OpenAiLlm
from aicore.llm.providers.openrouter import OpenRouterLlm
from aicore.llm.providers.grok import GrokLlm
from aicore.llm.providers.deepseek import DeepSeekLlm
from aicore.llm.providers.zai import ZaiLlm
from aicore.llm.providers.claude_code import ClaudeCodeLlm, RemoteClaudeCodeLlm
from aicore.llm.providers.base_provider import LlmBaseProvider

__all__ = [
    "AnthropicLlm",
    "GeminiLlm",
    "GroqLlm",
    "OpenAiLlm",
    "OpenRouterLlm",
    "GrokLlm",
    "MistralLlm",
    "NvidiaLlm",
    "DeepSeekLlm",
    "ZaiLlm",
    "ClaudeCodeLlm",
    "RemoteClaudeCodeLlm",
    "LlmBaseProvider"
]