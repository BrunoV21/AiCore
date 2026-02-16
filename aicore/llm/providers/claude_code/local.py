"""
aicore.llm.providers.claude_code.local
=======================================
Local Claude Code provider for AiCore.

This module contains:

ClaudeCodeBase
    Abstract base class shared by ``ClaudeCodeLlm`` (this module) and
    ``RemoteClaudeCodeLlm`` (remote.py).  Provides prompt serialisation,
    stream delta extraction, usage extraction, and the tool-event processing
    loop that both providers reuse.

ClaudeCodeLlm  (provider name: ``"claude_code"``)
    Drives the Claude Code CLI directly via ``claude-agent-sdk``'s ``query()``
    function.  Each ``acomplete()`` / ``complete()`` call is stateless — a
    fresh SDK session is created per call with internal tool chaining handled
    by ``max_turns``.

Design notes
------------
- **No API key required**: authentication is handled entirely by the Claude
  Code CLI (``claude login``).  ``api_key``, ``temperature``, and ``max_tokens``
  are silently ignored.
- **Streaming**: ``include_partial_messages=True`` is always set, enabling
  ``StreamEvent`` delivery so text and tool-call tokens are streamed in real
  time via ``stream_handler``.
- **Tool callbacks**: ``ClaudeCodeBase._process_message`` detects
  ``content_block_start`` (tool start) and ``ToolResultBlock`` (tool end)
  events and fires ``tool_callback`` with a typed dict containing
  ``stage``, ``tool_name``, ``tool_id``, ``is_error``, and ``content``.
- **MCP**: MCP servers are passed directly to ``ClaudeAgentOptions``; the
  base-class ``connect_to_mcp()`` is a deliberate no-op.

Prerequisites
-------------
::

    # 1. Node.js 18+ and the Claude Code CLI
    npm install -g @anthropic-ai/claude-code

    # 2. One-time authentication
    claude login

    # 3. Python SDK (included in core-for-ai dependencies)
    pip install core-for-ai

Supported config fields
-----------------------
Required:
    ``provider``  — ``"claude_code"``
    ``model``     — e.g. ``"claude-sonnet-4-5-20250929"``

Optional:
    ``permission_mode``  — ``"bypassPermissions"`` (default), ``"acceptEdits"``,
                           ``"default"``, or ``"plan"``
    ``cwd``              — working directory passed to the CLI
    ``max_turns``        — maximum number of agentic turns
    ``allowed_tools``    — list of tool names Claude may use
    ``cli_path``         — absolute path to the ``claude`` binary if not on PATH
    ``mcp_config_path``  — path to an MCP config JSON file

Example config (YAML)
---------------------
::

    llm:
      provider: "claude_code"
      model: "claude-sonnet-4-5-20250929"
      permission_mode: "bypassPermissions"
      cwd: "/path/to/project"
      max_turns: 10
      mcp_config_path: "./mcp_config.json"

Example usage (Python)
----------------------
::

    from aicore.llm import Llm
    from aicore.llm.config import LlmConfig

    llm = Llm.from_config(LlmConfig(
        provider="claude_code",
        model="claude-sonnet-4-5-20250929",
    ))

    # Async
    response = await llm.acomplete("List all Python files here")

    # Sync (must not already be inside a running event loop)
    response = llm.complete("List all Python files here")
"""

import asyncio
import contextlib
import inspect
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import tiktoken
from pydantic import BaseModel, RootModel, model_validator
from typing_extensions import Self

from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN, TOOL_CALL_END_TOKEN, TOOL_CALL_START_TOKEN
from aicore.logger import _logger
from aicore.llm.config import LlmConfig
from aicore.llm.mcp.models import ToolCallSchema
from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.logger import default_stream_handler

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _unset_env(*keys: str):
    """Temporarily remove environment variables for the duration of the block."""
    saved = {k: os.environ.pop(k) for k in keys if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


async def _call_handler(handler: Callable, token: str) -> None:
    """Call stream_handler whether it's sync or async."""
    if inspect.iscoroutinefunction(handler):
        await handler(token)
    else:
        handler(token)


class ClaudeCodeBase(LlmBaseProvider):
    """Abstract base class shared by ClaudeCodeLlm and RemoteClaudeCodeLlm."""

    # ------------------------------------------------------------------
    # Config validation is a no-op — auth is handled externally
    # ------------------------------------------------------------------
    def validate_config(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Reasoning is not applicable to this provider
    # ------------------------------------------------------------------
    def use_as_reasoner(self, *args, **kwargs):
        raise NotImplementedError(
            "ClaudeCodeLlm does not support use_as_reasoner(). "
            "The Claude Code CLI manages its own reasoning internally."
        )

    # ------------------------------------------------------------------
    # MCP: skip base-class tool conversion — SDK handles MCP natively
    # ------------------------------------------------------------------
    async def connect_to_mcp(self) -> None:
        """No-op: MCP servers are passed directly to ClaudeAgentOptions.mcp_servers."""
        pass

    # ------------------------------------------------------------------
    # Prompt serialisation
    # ------------------------------------------------------------------
    def _to_prompt_string(
        self,
        prompt: Union[str, BaseModel, RootModel, List],
    ) -> str:
        """Flatten the various prompt formats into a single string."""
        if isinstance(prompt, str):
            return prompt

        if isinstance(prompt, (BaseModel, RootModel)):
            return self.model_to_str(prompt)

        if isinstance(prompt, list):
            parts: List[str] = []
            for item in prompt:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, ToolCallSchema):
                    parts.append(f"[tool_call:{item.name}] {item.arguments}")
                elif isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if isinstance(content, list):
                        text_pieces = [
                            c.get("text", "") if isinstance(c, dict) else str(c)
                            for c in content
                        ]
                        content = " ".join(text_pieces)
                    parts.append(f"{role}: {content}")
                else:
                    parts.append(str(item))
            return "\n".join(parts)

        return str(prompt)

    # ------------------------------------------------------------------
    # Stream delta extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_stream_delta(event_msg: Any) -> Optional[str]:
        """Extract text delta from a StreamEvent."""
        raw = getattr(event_msg, "event", None)
        if not isinstance(raw, dict):
            return None
        if raw.get("type") != "content_block_delta":
            return None
        delta = raw.get("delta", {})
        if delta.get("type") == "text_delta":
            return delta.get("text", "")
        return None

    # ------------------------------------------------------------------
    # Text and usage extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_text_and_usage(
        messages: List[Any],
    ) -> tuple:
        """Return (text, input_tokens, output_tokens, cost, session_id)."""
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock  # noqa: PLC0415

        text_parts: List[str] = []
        input_tokens = 0
        output_tokens = 0
        cost: Optional[float] = None
        session_id: Optional[str] = None

        for msg in messages:
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(msg, ResultMessage):
                session_id = msg.session_id
                if msg.usage:
                    input_tokens = msg.usage.get("input_tokens", 0)
                    output_tokens = msg.usage.get("output_tokens", 0)
                if msg.total_cost_usd is not None:
                    cost = msg.total_cost_usd

        return "".join(text_parts), input_tokens, output_tokens, cost, session_id

    # ------------------------------------------------------------------
    # Tool-event processing loop (shared between local and remote)
    # ------------------------------------------------------------------
    async def _process_message(
        self,
        msg: Any,
        stream: bool,
        stream_handler: Callable,
        active_tools: Dict[str, str],
    ) -> None:
        """Process a single SDK message, handling tool events and stream deltas."""
        from claude_agent_sdk import UserMessage
        from claude_agent_sdk.types import StreamEvent, ToolResultBlock

        if isinstance(msg, StreamEvent):
            raw = msg.event

            # Detect tool call starting
            if raw.get("type") == "content_block_start":
                cb = raw.get("content_block", {})
                if cb.get("type") == "tool_use":
                    tool_name = cb.get("name", "unknown")
                    tool_id = cb.get("id", "")
                    active_tools[tool_id] = tool_name
                    _logger.logger.info(
                        f"Claude Code | Starting tool call: '{tool_name}' (id={tool_id})"
                    )
                    if self.tool_callback:
                        self.tool_callback({
                            "stage": "started",
                            "tool_name": tool_name,
                            "tool_id": tool_id,
                        })
                    await _call_handler(stream_handler, TOOL_CALL_START_TOKEN)

            # Stream text deltas
            elif stream:
                delta = self._extract_stream_delta(msg)
                if delta:
                    await _call_handler(stream_handler, delta)

        elif isinstance(msg, UserMessage):
            content = msg.content if isinstance(msg.content, list) else []
            for block in content:
                if isinstance(block, ToolResultBlock):
                    tool_name = active_tools.pop(block.tool_use_id, block.tool_use_id)
                    is_err = bool(block.is_error)
                    status = "error" if is_err else "success"
                    _logger.logger.info(
                        f"Claude Code | Tool '{tool_name}' concluded ({status})"
                    )
                    if self.tool_callback:
                        self.tool_callback({
                            "stage": "concluded",
                            "tool_name": tool_name,
                            "tool_id": block.tool_use_id,
                            "is_error": is_err,
                            "content": block.content,
                        })
                    await _call_handler(stream_handler, TOOL_CALL_END_TOKEN)


class ClaudeCodeLlm(ClaudeCodeBase):
    """LLM provider that drives Claude Code via the `claude-agent-sdk`."""

    @model_validator(mode="after")
    def _setup_claude_code(self) -> Self:
        # Check that the CLI is on PATH (or a custom path is provided)
        cli_path = getattr(self.config, "cli_path", None)
        if cli_path:
            resolved = Path(cli_path)
            if not resolved.exists():
                raise RuntimeError(
                    f"Claude Code CLI not found at {cli_path}. "
                    "Install it with: npm install -g @anthropic-ai/claude-code"
                )
        else:
            if shutil.which("claude") is None:
                raise RuntimeError(
                    "Claude Code CLI not found on PATH. "
                    "Install it with: npm install -g @anthropic-ai/claude-code"
                )

        # Set a tiktoken fallback tokenizer (cl100k_base covers claude models)
        try:
            self._tokenizer_fn = tiktoken.get_encoding("cl100k_base").encode
        except Exception:
            self._tokenizer_fn = None

        return self

    # ------------------------------------------------------------------
    # MCP bridge
    # ------------------------------------------------------------------
    def _build_mcp_servers(self) -> Any:
        """Return the mcp_servers value to pass to ClaudeAgentOptions."""
        mcp_config_path = getattr(self.config, "mcp_config_path", None)
        if mcp_config_path:
            return mcp_config_path  # SDK accepts a path string directly
        return {}

    # ------------------------------------------------------------------
    # Options builder
    # ------------------------------------------------------------------
    def _build_options(self) -> Any:
        """Map LlmConfig fields to ClaudeAgentOptions."""
        from claude_agent_sdk import ClaudeAgentOptions

        opts: Dict[str, Any] = {
            "model": self.config.model,
            "include_partial_messages": True,  # Enable StreamEvent for streaming
            "mcp_servers": self._build_mcp_servers(),
        }

        # Default to bypassPermissions so all tools are allowed unless the caller
        # explicitly restricts them via config.permission_mode.
        opts["permission_mode"] = self.config.permission_mode or "bypassPermissions"
        if self.config.cwd is not None:
            opts["cwd"] = self.config.cwd
        if self.config.max_turns is not None:
            opts["max_turns"] = self.config.max_turns
        if self.config.allowed_tools is not None:
            opts["allowed_tools"] = self.config.allowed_tools
        if self.config.cli_path is not None:
            opts["cli_path"] = self.config.cli_path

        return ClaudeAgentOptions(**opts)

    # ------------------------------------------------------------------
    # acomplete override
    # ------------------------------------------------------------------
    async def acomplete(
        self,
        prompt: Union[str, List, BaseModel, RootModel],
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path=None,
        json_output: bool = False,
        stream: bool = True,
        as_message_records: bool = False,
        stream_handler: Optional[Callable[[str], None]] = default_stream_handler,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
    ) -> Union[str, Dict, List]:
        from claude_agent_sdk import query, AssistantMessage, UserMessage
        from claude_agent_sdk.types import StreamEvent, ToolResultBlock
        from claude_agent_sdk._errors import CLIConnectionError, CLINotFoundError, ProcessError

        if prefix_prompt is not None:
            logger.warning(
                "ClaudeCodeLlm: prefix_prompt is not supported by query() and will be ignored."
            )
        if img_path is not None:
            logger.warning(
                "ClaudeCodeLlm: img_path is not supported in this version and will be ignored."
            )

        await self.connect_to_mcp()

        prompt_str = self._to_prompt_string(prompt)
        options = self._build_options()

        # Inject system_prompt if provided
        if system_prompt:
            if isinstance(system_prompt, list):
                system_prompt = "\n".join(system_prompt)
            options.system_prompt = system_prompt

        stream_handler = stream_handler or default_stream_handler

        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        cost: Optional[float] = None
        output: Optional[str] = None
        error_message: Optional[str] = None
        collected_messages: List[Any] = []

        # Maps tool_id -> tool_name for active tool calls
        _active_tools: Dict[str, str] = {}

        try:
            if stream:
                await _call_handler(stream_handler, STREAM_START_TOKEN)

            with _unset_env("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
                async for msg in query(prompt=prompt_str, options=options):
                    collected_messages.append(msg)
                    await self._process_message(msg, stream, stream_handler, _active_tools)

            if stream:
                await _call_handler(stream_handler, STREAM_END_TOKEN)

            output, input_tokens, output_tokens, cost, sdk_session_id = (
                self._extract_text_and_usage(collected_messages)
            )

            if sdk_session_id:
                self.session_id = sdk_session_id

            if self.usage:
                self.usage.record_completion(
                    prompt_tokens=input_tokens,
                    response_tokens=output_tokens,
                    completion_id=sdk_session_id or self.session_id,
                )

            if json_output:
                output = self.extract_json(output)

        except (CLINotFoundError, CLIConnectionError, ProcessError) as e:
            error_message = str(e)
            raise RuntimeError(error_message) from e
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            if self.collector:
                completion_args: Dict[str, Any] = {
                    "provider": self.config.provider,
                    "model": self.config.model,
                    "prompt": prompt_str,
                }
                await self.collector.arecord_completion(
                    provider=self.config.provider,
                    operation_type="completion",
                    completion_args=completion_args,
                    response=output,
                    session_id=self.session_id,
                    workspace=self.worspace,
                    agent_id=agent_id or self.agent_id,
                    action_id=action_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost or 0,
                    latency_ms=latency_ms,
                    error_message=error_message,
                    extras=self.extras,
                )

        if as_message_records:
            return [{"role": "assistant", "content": output}]

        return output

    # ------------------------------------------------------------------
    # complete override — synchronous wrapper
    # ------------------------------------------------------------------
    def complete(
        self,
        prompt: Union[str, List, BaseModel, RootModel],
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path=None,
        json_output: bool = False,
        stream: bool = True,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None,
    ) -> Union[str, Dict]:
        """Synchronous wrapper around acomplete().

        Note: Callers already inside a running event loop must use acomplete() directly.
        """
        return asyncio.run(
            self.acomplete(
                prompt=prompt,
                system_prompt=system_prompt,
                prefix_prompt=prefix_prompt,
                img_path=img_path,
                json_output=json_output,
                stream=stream,
                agent_id=agent_id,
                action_id=action_id,
            )
        )
