"""
aicore.llm.providers.claude_code.remote
=========================================
Remote Claude Code provider for AiCore.

This module contains:

RemoteClaudeCodeLlm  (provider name: ``"remote_claude_code"``)
    Connects to a running **Claude Code Proxy Server** over HTTP SSE and
    reconstructs the SDK message stream locally, giving callers the identical
    ``acomplete()`` / ``complete()`` interface as ``ClaudeCodeLlm``.

    Use this provider when the Claude Code CLI lives on a different machine
    (e.g. a dev box, a server, or a shared service) and AiCore runs in an
    environment that cannot execute the CLI directly.

How it works
------------
1. ``acomplete()`` serialises the prompt and options into a JSON request body.
2. ``_iter_sse()`` opens a persistent HTTP POST to ``{base_url}/query`` with
   Bearer authentication and yields ``(event_type, data_dict)`` pairs from the
   SSE stream returned by the proxy.
3. ``_deserialize_message()`` reconstructs typed ``claude-agent-sdk`` message
   objects (``AssistantMessage``, ``UserMessage``, ``ResultMessage``,
   ``StreamEvent``, …) from the raw SSE frame data.
4. The reconstructed messages are fed through ``ClaudeCodeBase._process_message``
   — the same tool-event loop used by the local provider — so tool callbacks,
   ``TOOL_CALL_START_TOKEN`` / ``TOOL_CALL_END_TOKEN``, and streaming deltas
   all behave identically.

Proxy server
------------
Start the proxy on the machine that has the Claude Code CLI::

    # Install server-side dependencies
    pip install core-for-ai[claude-server]
    npm install -g @anthropic-ai/claude-code
    claude login

    # Launch
    aicore-proxy-server --port 8080 --tunnel none
    # or
    python -m aicore.scripts.claude_code_proxy_server --port 8080

The server prints the generated ``CLAUDE_PROXY_TOKEN`` (Bearer token) at
startup.  Pass this as ``api_key`` in the client config.

Prerequisites (client-side only)
---------------------------------
::

    pip install core-for-ai   # no CLI or server extras required

Supported config fields
-----------------------
Required:
    ``provider``   — ``"remote_claude_code"``
    ``model``      — e.g. ``"claude-sonnet-4-5-20250929"``
    ``base_url``   — URL of the proxy server, e.g. ``"http://host:8080"``
    ``api_key``    — ``CLAUDE_PROXY_TOKEN`` printed at proxy startup

Optional (forwarded to the proxy):
    ``permission_mode``    — ``"bypassPermissions"`` (default), ``"acceptEdits"``, …
    ``cwd``                — working directory; must be in ``--allowed-cwd-paths``
    ``max_turns``          — maximum number of agentic turns
    ``allowed_tools``      — list of tool names Claude may use
    ``skip_health_check``  — skip the ``GET /health`` check at startup
                             (default ``false``)

Note: ``cli_path`` is a server-side concern and is intentionally excluded from
the request body even if set in the config.

Example config (YAML)
---------------------
::

    llm:
      provider: "remote_claude_code"
      model: "claude-sonnet-4-5-20250929"
      base_url: "http://your-proxy-host:8080"
      api_key: "your_proxy_token"
      permission_mode: "bypassPermissions"
      cwd: "/path/to/project"
      max_turns: 10
      skip_health_check: false

Example usage (Python)
----------------------
::

    from aicore.llm import Llm
    from aicore.llm.config import LlmConfig

    llm = Llm.from_config(LlmConfig(
        provider="remote_claude_code",
        model="claude-sonnet-4-5-20250929",
        base_url="http://your-proxy-host:8080",
        api_key="your_proxy_token",
    ))

    # Async
    response = await llm.acomplete("Summarise this codebase")

    # Sync (must not already be inside a running event loop)
    response = llm.complete("Summarise this codebase")

Known limitations
-----------------
- SSE reconnection (``Last-Event-ID``) is tracked but not used for auto-retry.
- MCP server config is a proxy-side concern; ``connect_to_mcp()`` is a no-op.
- The synchronous ``complete()`` wrapper uses ``asyncio.run()``; callers already
  inside a running event loop must use ``acomplete()`` directly.
- ``ThinkingBlock`` reconstruction depends on the installed ``claude-agent-sdk``
  version; falls back to ``TextBlock`` if unavailable.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union

import httpx
import tiktoken
from pydantic import BaseModel, RootModel, model_validator
from typing_extensions import Self

from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN, TOOL_CALL_END_TOKEN, TOOL_CALL_START_TOKEN
from aicore.llm.config import LlmConfig
from aicore.llm.providers.claude_code.local import ClaudeCodeBase, _call_handler
from aicore.logger import default_stream_handler

logger = logging.getLogger(__name__)


class RemoteClaudeCodeLlm(ClaudeCodeBase):
    """LLM provider that connects to a Claude Code Proxy Server over HTTP SSE."""

    # Tracks the last SSE event id for potential reconnection support (future use)
    _last_sse_id: Optional[str] = None

    @model_validator(mode="after")
    def _setup_remote_claude_code(self) -> Self:
        if not getattr(self.config, "base_url", None):
            raise ValueError(
                "RemoteClaudeCodeLlm requires 'base_url' to be set in LlmConfig.\n"
                "Set it to your proxy server URL, e.g.: base_url: \"http://localhost:8080\"\n"
                "Start the proxy server with: aicore-proxy-server --port 8080\n"
                "See docs/claude_code_proxy_server_plan.md for how to start the proxy server."
            )

        if not getattr(self.config, "api_key", None):
            raise ValueError(
                "RemoteClaudeCodeLlm requires 'api_key' to be set in LlmConfig.\n"
                "Set it to the Bearer token of your proxy server (CLAUDE_PROXY_TOKEN)."
            )

        # Set a tiktoken fallback tokenizer (cl100k_base covers claude models)
        try:
            self._tokenizer_fn = tiktoken.get_encoding("cl100k_base").encode
        except Exception:
            self._tokenizer_fn = None

        if not self.config.skip_health_check:
            self._check_server_health()

        return self

    # ------------------------------------------------------------------
    # Server health check on initialisation
    # ------------------------------------------------------------------
    def _check_server_health(self) -> None:
        """Perform a GET /health check against the proxy server."""
        base_url = self.config.base_url.rstrip("/")
        try:
            response = httpx.get(f"{base_url}/health", timeout=3.0)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise ConnectionError(
                f"Cannot connect to the Claude Code Proxy Server at {base_url}.\n"
                "Is it running? Start it with:\n"
                "  aicore-proxy-server --port 8080\n"
                "See docs/claude_code_proxy_server_plan.md for setup instructions.\n"
                "To skip this check, set skip_health_check: true in your config."
            ) from e

        if response.status_code != 200:
            raise RuntimeError(
                f"Proxy server at {base_url} returned unexpected status "
                f"{response.status_code} on /health check."
            )

        logger.debug(f"RemoteClaudeCodeLlm: proxy server health check passed ({base_url})")

    # ------------------------------------------------------------------
    # Request body builder
    # ------------------------------------------------------------------
    def _build_request_body(
        self, prompt_str: str, system_prompt: Optional[str]
    ) -> dict:
        """Build the JSON-serialisable request body for the proxy server."""
        options: Dict[str, Any] = {}

        if self.config.model is not None:
            options["model"] = self.config.model
        if self.config.permission_mode is not None:
            options["permission_mode"] = self.config.permission_mode
        if self.config.cwd is not None:
            options["cwd"] = self.config.cwd
        if self.config.max_turns is not None:
            options["max_turns"] = self.config.max_turns
        if self.config.permissions is not None:
            options["config"] = self.config.permissions
        if self.config.allowed_tools is not None:
            options["allowed_tools"] = self.config.allowed_tools
        # cli_path is a server-side concern and must NOT be sent to the proxy

        body: Dict[str, Any] = {
            "prompt": prompt_str,
            "options": options,
        }
        if system_prompt is not None:
            body["system_prompt"] = system_prompt

        return body

    # ------------------------------------------------------------------
    # Async SSE client generator
    # ------------------------------------------------------------------
    async def _iter_sse(self, body: dict):
        """Yield (event_type, data_dict) pairs from the proxy server SSE stream."""
        base_url = self.config.base_url.rstrip("/")
        url = f"{base_url}/query"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            try:
                client = httpx.AsyncClient(timeout=None, http2=True)
            except Exception:
                logger.warning(
                    "RemoteClaudeCodeLlm: httpx HTTP/2 support unavailable, falling back to HTTP/1.1"
                )
                client = httpx.AsyncClient(timeout=None)

            async with client:
                async with client.stream(
                    "POST", url, content=json.dumps(body), headers=headers
                ) as response:
                    if response.status_code == 401:
                        raise PermissionError(
                            f"Proxy server rejected the Bearer token. "
                            f"Check CLAUDE_PROXY_TOKEN on the server and 'api_key' in your config. "
                            f"Server: {self.config.base_url}"
                        )
                    if response.status_code == 403:
                        text = await response.aread()
                        raise PermissionError(
                            f"Proxy server rejected the requested cwd — it is not in the server's "
                            f"allowed-cwd-paths whitelist. Server response: {text.decode()}"
                        )
                    if response.status_code == 422:
                        text = await response.aread()
                        raise ValueError(
                            f"Proxy server rejected the request body (validation error): "
                            f"{text.decode()}"
                        )
                    if response.status_code >= 400:
                        text = await response.aread()
                        raise RuntimeError(
                            f"Proxy server returned HTTP {response.status_code}: {text.decode()}"
                        )

                    # Parse SSE frames line-by-line
                    event_type: Optional[str] = None
                    data_str: Optional[str] = None
                    event_id: Optional[str] = None

                    async for line in response.aiter_lines():
                        if line.startswith("event:"):
                            event_type = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            data_str = line[len("data:"):].strip()
                        elif line.startswith("id:"):
                            event_id = line[len("id:"):].strip()
                            self._last_sse_id = event_id
                        elif line == "":
                            # Blank line signals end of frame
                            if data_str:
                                try:
                                    data_dict = json.loads(data_str)
                                except json.JSONDecodeError:
                                    data_dict = {"raw": data_str}
                                yield (event_type or "unknown", data_dict)
                            # Reset buffer
                            event_type = None
                            data_str = None
                            event_id = None

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise ConnectionError(
                f"Could not connect to the proxy server at {self.config.base_url}. "
                "Is it running? Start it with: aicore-proxy-server"
            ) from e

    # ------------------------------------------------------------------
    # SSE frame deserialiser
    # ------------------------------------------------------------------
    @staticmethod
    def _deserialize_message(event_type: str, data: dict) -> Any:
        """Reconstruct an SDK message object from an SSE frame."""
        try:
            from claude_agent_sdk import AssistantMessage, UserMessage, ResultMessage, SystemMessage
            from claude_agent_sdk.types import StreamEvent, TextBlock, ToolUseBlock, ToolResultBlock

            if event_type == "stream_event":
                return StreamEvent(
                    uuid=data.get("uuid", ""),
                    session_id=data.get("session_id", ""),
                    event=data.get("event", {}),
                    parent_tool_use_id=data.get("parent_tool_use_id"),
                )

            elif event_type == "assistant_message":
                content_blocks = []
                for block in data.get("content", []):
                    btype = block.get("type")
                    if btype == "text":
                        content_blocks.append(TextBlock(text=block["text"]))
                    elif btype == "tool_use":
                        content_blocks.append(ToolUseBlock(
                            id=block["id"],
                            name=block["name"],
                            input=block["input"],
                        ))
                    elif btype == "thinking":
                        try:
                            from claude_agent_sdk.types import ThinkingBlock
                            content_blocks.append(ThinkingBlock(
                                thinking=block["thinking"],
                                signature=block.get("signature", ""),
                            ))
                        except (ImportError, KeyError):
                            logger.debug(
                                f"RemoteClaudeCodeLlm: ThinkingBlock not available or malformed; "
                                f"treating as TextBlock: {block}"
                            )
                            content_blocks.append(TextBlock(text=block.get("thinking", "")))
                    else:
                        logger.warning(
                            f"RemoteClaudeCodeLlm: unknown content block type '{btype}' in "
                            f"assistant_message; skipping."
                        )
                return AssistantMessage(
                    content=content_blocks,
                    model=data.get("model", ""),
                    parent_tool_use_id=data.get("parent_tool_use_id"),
                )

            elif event_type == "user_message":
                content_raw = data.get("content", [])
                if isinstance(content_raw, str):
                    return UserMessage(content=content_raw)
                content_blocks = []
                for block in content_raw:
                    btype = block.get("type")
                    if btype == "text":
                        content_blocks.append(TextBlock(text=block["text"]))
                    elif btype == "tool_use":
                        content_blocks.append(ToolUseBlock(
                            id=block["id"],
                            name=block["name"],
                            input=block["input"],
                        ))
                    elif btype == "tool_result":
                        content_blocks.append(ToolResultBlock(
                            tool_use_id=block["tool_use_id"],
                            content=block.get("content"),
                            is_error=block.get("is_error", False),
                        ))
                    elif btype == "thinking":
                        try:
                            from claude_agent_sdk.types import ThinkingBlock
                            content_blocks.append(ThinkingBlock(
                                thinking=block["thinking"],
                                signature=block.get("signature", ""),
                            ))
                        except (ImportError, KeyError):
                            content_blocks.append(TextBlock(text=block.get("thinking", "")))
                    else:
                        logger.warning(
                            f"RemoteClaudeCodeLlm: unknown content block type '{btype}' in "
                            f"user_message; skipping."
                        )
                return UserMessage(
                    content=content_blocks,
                    uuid=data.get("uuid"),
                    parent_tool_use_id=data.get("parent_tool_use_id"),
                )

            elif event_type == "result_message":
                return ResultMessage(
                    subtype=data.get("subtype", "result"),
                    duration_ms=data.get("duration_ms", 0),
                    duration_api_ms=data.get("duration_api_ms", 0),
                    is_error=data.get("is_error", False),
                    num_turns=data.get("num_turns", 0),
                    session_id=data["session_id"],
                    total_cost_usd=data.get("total_cost_usd"),
                    usage=data.get("usage"),
                    result=data.get("result"),
                )

            elif event_type == "system_message":
                return SystemMessage(
                    subtype=data.get("subtype", ""),
                    data=data.get("data", data),
                )

            elif event_type == "error":
                raise RuntimeError(
                    f"Proxy server stream error: {data.get('message', 'unknown error')} "
                    f"(exit_code={data.get('exit_code')})"
                )

            else:
                logger.debug(
                    f"RemoteClaudeCodeLlm: unrecognised SSE event type '{event_type}'; skipping."
                )
                return None

        except RuntimeError:
            raise
        except Exception as e:
            logger.debug(
                f"RemoteClaudeCodeLlm: failed to deserialize SSE frame event_type={event_type}: {e}"
            )
            raise ValueError(
                f"Failed to deserialize SSE frame event_type={event_type}: {e}"
            ) from e

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
        if prefix_prompt is not None:
            logger.warning(
                "RemoteClaudeCodeLlm: prefix_prompt is not supported and will be ignored."
            )
        if img_path is not None:
            logger.warning(
                "RemoteClaudeCodeLlm: img_path is not supported in this version and will be ignored."
            )

        prompt_str = self._to_prompt_string(prompt)

        # Flatten system_prompt list if needed
        if isinstance(system_prompt, list):
            system_prompt = "\n".join(system_prompt)

        body = self._build_request_body(prompt_str, system_prompt)

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

            async for event_type, data_dict in self._iter_sse(body):
                msg = self._deserialize_message(event_type, data_dict)
                if msg is None:
                    continue
                collected_messages.append(msg)
                await self._process_message(msg, stream, stream_handler, _active_tools)

            if stream:
                await _call_handler(stream_handler, STREAM_END_TOKEN)

            output, input_tokens, output_tokens, cost, sdk_session_id, message_records = (
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

        except (ConnectionError, PermissionError, ValueError, RuntimeError):
            error_message = str(
                ConnectionError.__doc__
                if isinstance(Exception, ConnectionError)
                else ""
            )
            raise
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
            return message_records

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
