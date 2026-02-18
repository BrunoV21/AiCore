# Remote Claude Code Provider — Implementation Checklist

> **Purpose:** Implement `RemoteClaudeCodeLlm` (provider name: `"remote_claude_code"`), a new AiCore LLM provider that connects to the Claude Code Proxy Server defined in `claude_code_proxy_server_plan.md`. The provider speaks to the proxy over HTTP SSE and reconstructs the SDK message stream locally, giving callers the identical interface they already use with `ClaudeCodeLlm`.
>
> **New file:** `aicore/llm/providers/remote_claude_code.py`
> **Modified files:** `aicore/llm/config.py`, `aicore/llm/providers/__init__.py`, `aicore/llm/llm.py`, `aicore/models_metadata.json`
> **New files:** `config/config_example_remote_claude_code.yml`, `tests/test_remote_claude_code.py`

---

## 1. Shared Base Class: `ClaudeCodeBase` in `aicore/llm/providers/claude_code.py`

The goal of this refactor is to extract all logic that `ClaudeCodeLlm` and `RemoteClaudeCodeLlm` share into a common abstract base class so neither provider duplicates code.

### 1.1 Create `ClaudeCodeBase(LlmBaseProvider)`

- [x] Define `class ClaudeCodeBase(LlmBaseProvider)` in `aicore/llm/providers/claude_code.py`, above the existing `ClaudeCodeLlm` definition.
- [x] Move the following methods verbatim from `ClaudeCodeLlm` into `ClaudeCodeBase` (they contain no CLI-specific logic):
  - [x] `validate_config(self) -> None` — no-op; auth handled externally (by CLI or by proxy token).
  - [x] `use_as_reasoner(self, *args, **kwargs)` — raises `NotImplementedError` with the existing message.
  - [x] `connect_to_mcp(self) -> None` — async no-op; MCP servers are passed directly to options.
  - [x] `_to_prompt_string(self, prompt)` — the full flattening logic for `str | BaseModel | RootModel | list` inputs.
  - [x] `_extract_stream_delta(event_msg)` — static method; extracts `text_delta` text from a `StreamEvent`.
  - [x] `_extract_text_and_usage(messages)` — static method; iterates collected messages and returns `(text, input_tokens, output_tokens, cost, session_id)`.
- [x] Keep `_unset_env(*keys)` as a **module-level** context manager (not a method). Both `ClaudeCodeLlm` and `RemoteClaudeCodeLlm` import it from this module.
- [x] Keep `_call_handler(handler, token)` as a **module-level** async helper (not a method). Both providers use it.

### 1.2 Extract the Tool-Event Processing Loop

- [x] Define `async def _process_message(self, msg, stream: bool, stream_handler, active_tools: dict) -> None` on `ClaudeCodeBase`.
- [x] Move the entire `if isinstance(msg, StreamEvent) ... elif isinstance(msg, UserMessage) ...` block from `ClaudeCodeLlm.acomplete()` into this method. The method should:
  - Handle `StreamEvent` with `content_block_start` → detect tool call start, log it, call `self.tool_callback`, call `_call_handler(stream_handler, TOOL_CALL_START_TOKEN)`.
  - Handle `StreamEvent` with `content_block_delta` and `text_delta` → call `_call_handler(stream_handler, delta)` if `stream` is True.
  - Handle `UserMessage` containing `ToolResultBlock` items → log tool conclusion, call `self.tool_callback`, call `_call_handler(stream_handler, TOOL_CALL_END_TOKEN)`.
- [x] `ClaudeCodeLlm.acomplete()` replaces its inline message-processing block with a call to `await self._process_message(msg, stream, stream_handler, _active_tools)`.
- [x] `RemoteClaudeCodeLlm.acomplete()` calls the same method after deserialising each SSE frame.

### 1.3 Update `ClaudeCodeLlm` to Inherit from `ClaudeCodeBase`

- [x] Change the class declaration to `class ClaudeCodeLlm(ClaudeCodeBase)`.
- [x] `ClaudeCodeLlm` retains only the parts that are CLI-specific:
  - [x] `_setup_claude_code` model_validator (CLI PATH check and tiktoken setup).
  - [x] `_build_mcp_servers()` method.
  - [x] `_build_options()` method that constructs `ClaudeAgentOptions`.
  - [x] `acomplete()` — now calls `_process_message()` from the base class instead of inline logic.
  - [x] `complete()` — synchronous wrapper unchanged.
- [x] Verify that all existing `ClaudeCodeLlm` tests still pass after the refactor (no behaviour change intended).

---

## 2. Config (`aicore/llm/config.py`)

- [x] Add `"remote_claude_code"` to the `provider` `Literal` type. The full updated type should be:
  ```python
  Literal["anthropic", "gemini", "groq", "mistral", "nvidia", "openai", "openrouter",
          "deepseek", "grok", "zai", "claude_code", "remote_claude_code"]
  ```
- [x] Confirm that the existing `base_url: Optional[str] = None` field (already present in `LlmConfig`) is used as the proxy server URL for `remote_claude_code`. No new field addition is needed for this; document it with a comment:
  ```python
  # For remote_claude_code: base_url is the proxy server URL (e.g. "http://localhost:8080")
  ```
- [x] Confirm that the existing `api_key: Optional[str] = None` field is used as the Bearer token. Add a comment:
  ```python
  # For remote_claude_code: api_key is used as the Bearer token for the proxy server
  ```
- [x] Confirm that all existing `claude_code`-specific fields are also valid for `remote_claude_code` and will be included in the request body options sent to the proxy:
  - [x] `permission_mode: Optional[str]`
  - [x] `cwd: Optional[str]`
  - [x] `max_turns: Optional[int]`
  - [x] `allowed_tools: Optional[List[str]]`
  - [x] `cli_path: Optional[str]` — note in a comment that this field is **ignored** by `RemoteClaudeCodeLlm`; it is server-side only and should not be sent in the request body.
- [x] Add an optional `skip_health_check: Optional[bool] = False` field to `LlmConfig` with a comment:
  ```python
  # remote_claude_code: set True to skip the startup GET /health connectivity check
  # (useful in production or when the proxy server is known to be up)
  ```

---

## 3. New Provider File `aicore/llm/providers/remote_claude_code.py`

### 3.1 Class Definition

- [x] Define `class RemoteClaudeCodeLlm(ClaudeCodeBase)` importing `ClaudeCodeBase` from `.claude_code`.
- [x] Import all required types at the top of the file:
  - From `claude_agent_sdk`: `AssistantMessage`, `UserMessage`, `ResultMessage`, `SystemMessage`
  - From `claude_agent_sdk.types`: `StreamEvent`, `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, `ThinkingBlock`
  - Standard library: `asyncio`, `base64`, `json`, `logging`, `time`
  - Third-party: `httpx`
  - AiCore: `LlmConfig`, `ClaudeCodeBase`, `_call_handler`, `STREAM_START_TOKEN`, `STREAM_END_TOKEN`, `TOOL_CALL_START_TOKEN`, `TOOL_CALL_END_TOKEN`
- [x] Add a tiktoken fallback tokenizer in the model_validator (same pattern as `ClaudeCodeLlm._setup_claude_code`):
  ```python
  try:
      self._tokenizer_fn = tiktoken.get_encoding("cl100k_base").encode
  except Exception:
      self._tokenizer_fn = None
  ```
- [x] Add a `@model_validator(mode="after")` named `_setup_remote_claude_code` that:
  - [x] Checks `self.config.base_url` is set and non-empty. If not, raises `ValueError`:
    ```
    RemoteClaudeCodeLlm requires 'base_url' to be set in LlmConfig.
    Set it to your proxy server URL, e.g.: base_url: "http://localhost:8080"
    See docs/claude_code_proxy_server_plan.md for how to start the proxy server.
    ```
  - [x] Checks `self.config.api_key` is set and non-empty. If not, raises `ValueError`:
    ```
    RemoteClaudeCodeLlm requires 'api_key' to be set in LlmConfig.
    Set it to the Bearer token of your proxy server (CLAUDE_PROXY_TOKEN).
    ```
  - [x] If `self.config.skip_health_check` is not `True`, calls `_check_server_health()` (see section 7).
  - [x] Returns `self`.

### 3.2 `_build_request_body(self, prompt_str: str, system_prompt: Optional[str]) -> dict`

- [x] Build and return the JSON-serialisable request body dict.
- [x] Top-level keys:
  - `"prompt"`: the prompt string.
  - `"system_prompt"`: the system_prompt string, or omit key if `None`.
  - `"options"`: a dict built from all non-`None` `claude_code`-relevant config fields.
- [x] Options dict must include (only when the field is not `None`):
  - [x] `"model"`: `self.config.model`
  - [x] `"permission_mode"`: `self.config.permission_mode`
  - [x] `"cwd"`: `self.config.cwd`
  - [x] `"max_turns"`: `self.config.max_turns`
  - [x] `"allowed_tools"`: `self.config.allowed_tools`
- [x] **Do not** include `cli_path` in the options dict — it is a server-side concern only.
- [x] The server will always force `include_partial_messages: True`; do not duplicate it in the client body (to avoid confusion, but it is harmless if present).

### 3.3 `_iter_sse(self, body: dict)` — Async SSE Client Generator

- [x] Define as `async def _iter_sse(self, body: dict)` yielding `tuple[str, dict]` pairs of `(event_type, data_dict)`.
- [x] Create an `httpx.AsyncClient(timeout=None, http2=True)` inside an `async with` block (the `timeout=None` is critical — streams can run for minutes).
  - If `httpx` was not installed with HTTP/2 support, catch the error and fall back to `http2=False` with a logged warning.
- [x] Set the `Authorization: Bearer {self.config.api_key}` header on the request.
- [x] POST to `f"{self.config.base_url.rstrip('/')}/query"` with `content=json.dumps(body)` and header `Content-Type: application/json`.
- [x] Use `async with client.stream("POST", url, ...)` to process the response without buffering it entirely.
- [x] Before beginning to parse frames, check `response.status_code`:
  - 401 → raise `PermissionError(f"Proxy server rejected the Bearer token. Check CLAUDE_PROXY_TOKEN on the server and 'api_key' in your config. Server: {self.config.base_url}")`.
  - 403 → raise `PermissionError(f"Proxy server rejected the requested cwd — it is not in the server's allowed-cwd-paths whitelist. Server response: {response.text}")`.
  - 422 → raise `ValueError(f"Proxy server rejected the request body (validation error): {response.text}")`.
  - Any other 4xx/5xx → raise `RuntimeError(f"Proxy server returned HTTP {response.status_code}: {response.text}")`.
- [x] Parse SSE frames by accumulating lines into a buffer. When a blank line is encountered, process the buffered lines:
  - Extract `event_type` from the `event:` line (strip the prefix and whitespace).
  - Extract `data_str` from the `data:` line (strip the prefix and whitespace).
  - Extract `last_event_id` from the `id:` line (store on `self._last_sse_id` for potential reconnection support).
  - If `data_str` is non-empty, parse `data_dict = json.loads(data_str)`.
  - Yield `(event_type, data_dict)`.
  - Reset the buffer.
- [x] If an `httpx.ConnectError` or `httpx.ConnectTimeout` is raised, re-raise as `ConnectionError(f"Could not connect to the proxy server at {self.config.base_url}. Is it running? Start it with: python -m aicore.llm.providers.claude_code_proxy_server")`.

### 3.4 `_deserialize_message(event_type: str, data: dict) -> Any` — Static Method

- [x] Define as `@staticmethod` returning one of the SDK message types or raising `RuntimeError`.
- [x] Dispatch on `event_type`:
  - `"stream_event"` → reconstruct a `StreamEvent`. The `data` dict should have an `"event"` key containing the raw event dict. Construct: `StreamEvent(event=data["event"])` (check the SDK dataclass signature; add any other required fields).
  - `"assistant_message"` → reconstruct `AssistantMessage`. The `data` dict has a `"content"` list. Reconstruct content blocks by dispatching on `block["type"]`:
    - `"text"` → `TextBlock(type="text", text=block["text"])`
    - `"tool_use"` → `ToolUseBlock(type="tool_use", id=block["id"], name=block["name"], input=block["input"])`
    - `"thinking"` → `ThinkingBlock(type="thinking", thinking=block["thinking"])` (if supported by SDK version)
    - Unknown block type → log a warning and skip.
  - `"user_message"` → reconstruct `UserMessage`. Content blocks follow the same dispatch pattern; additionally handle:
    - `"tool_result"` → `ToolResultBlock(type="tool_result", tool_use_id=block["tool_use_id"], content=block.get("content"), is_error=block.get("is_error", False))`
  - `"result_message"` → reconstruct `ResultMessage(session_id=data["session_id"], total_cost_usd=data.get("total_cost_usd"), usage=data.get("usage"), num_turns=data.get("num_turns"), is_error=data.get("is_error", False))`.
  - `"system_message"` → reconstruct `SystemMessage` from `data` (check SDK for exact fields).
  - `"error"` → raise `RuntimeError(f"Proxy server stream error: {data.get('message', 'unknown error')} (exit_code={data.get('exit_code')})")`.
  - Any unknown event type → log a warning at `DEBUG` level and return `None` (the caller skips `None` values).
- [x] Wrap the entire method body in a broad `except Exception` that logs `DEBUG`-level detail and re-raises as `ValueError(f"Failed to deserialize SSE frame event_type={event_type}: {e}")` so the caller can emit an error event.

### 3.5 `acomplete()` Override

- [x] Signature must match `ClaudeCodeLlm.acomplete()` exactly so the two providers are interchangeable at the `Llm` layer.
- [x] Log the same unsupported-argument warnings as `ClaudeCodeLlm` for `prefix_prompt` and `img_path`.
- [x] Convert the prompt to a string using `self._to_prompt_string(prompt)` (inherited from `ClaudeCodeBase`).
- [x] Build the request body with `self._build_request_body(prompt_str, system_prompt)`.
- [x] Initialise `collected_messages`, `_active_tools`, `start_time`, `input_tokens`, `output_tokens`, `cost`, `output`, `error_message` the same way as `ClaudeCodeLlm.acomplete()`.
- [x] Call `await _call_handler(stream_handler, STREAM_START_TOKEN)` if `stream` is True.
- [x] Iterate `self._iter_sse(body)` inside a `try` block:
  - For each `(event_type, data_dict)`:
    - Call `msg = self._deserialize_message(event_type, data_dict)`.
    - If `msg` is `None`, continue (unknown/unhandled event type).
    - Append `msg` to `collected_messages`.
    - Call `await self._process_message(msg, stream, stream_handler, _active_tools)` (inherited from `ClaudeCodeBase`).
- [x] Call `await _call_handler(stream_handler, STREAM_END_TOKEN)` if `stream` is True.
- [x] Call `self._extract_text_and_usage(collected_messages)` to get `(output, input_tokens, output_tokens, cost, sdk_session_id)`.
- [x] Record the session_id, usage, observability collector call, json_output extraction, and `as_message_records` return — all **identical** to `ClaudeCodeLlm.acomplete()`. Do not abbreviate or skip any of these blocks; they must be character-for-character equivalent so both providers are observable in the same way.
- [x] In the `except` block, catch `(ConnectionError, PermissionError, ValueError, RuntimeError)` and re-raise with the original message (they are already descriptive).
- [x] In the `finally` block, record latency and call `self.collector.arecord_completion(...)` exactly as `ClaudeCodeLlm` does, substituting `self.config.provider` which will be `"remote_claude_code"`.

### 3.6 `complete()` Override

- [x] Synchronous wrapper via `asyncio.run(self.acomplete(...))` — identical pattern to `ClaudeCodeLlm.complete()`.
- [x] Include the same docstring warning: "Callers already inside a running event loop must use `acomplete()` directly."

---

## 4. Registration

- [x] `aicore/llm/providers/__init__.py`:
  - [x] Add `from aicore.llm.providers.remote_claude_code import RemoteClaudeCodeLlm`.
  - [x] Add `"RemoteClaudeCodeLlm"` to the `__all__` list.

- [x] `aicore/llm/llm.py`:
  - [x] Add `RemoteClaudeCodeLlm` to the import from `aicore.llm.providers`.
  - [x] Add a new enum member to `Providers`:
    ```python
    REMOTE_CLAUDE_CODE: RemoteClaudeCodeLlm = RemoteClaudeCodeLlm
    ```
  - [x] The `start_provider` model_validator in `Llm` already calls `Providers[self.config.provider.upper()].get_instance(self.config)`, so no further changes to `Llm` are needed — the new member will be picked up automatically.

---

## 5. Models Metadata (`aicore/models_metadata.json`)

- [x] For each existing `claude_code-{model_name}` entry in `models_metadata.json`, add a corresponding `remote_claude_code-{model_name}` entry with:
  - [x] `max_tokens`: same value as the `claude_code` counterpart.
  - [x] `context_window`: same value as the `claude_code` counterpart.
  - [x] `tool_use`: `true` (same as `claude_code`).
  - [x] `pricing`: `null` — cost is reported via `ResultMessage.total_cost_usd` from the proxy, not calculated locally.
- [x] Ensure that every model name supported by `ClaudeCodeLlm` also has a `remote_claude_code` entry so users get proper token limit enforcement on the client side even when using the remote provider.
- [x] Add a JSON comment (or a `"_note"` field if comments are not supported) documenting: "remote_claude_code entries mirror claude_code; pricing is always null because cost is reported by the proxy server via ResultMessage."

---

## 6. Example Config (`config/config_example_remote_claude_code.yml`)

- [x] Create `config/config_example_remote_claude_code.yml` with the following structure and comments:

  ```yaml
  llm:
    provider: remote_claude_code

    # URL of the running Claude Code Proxy Server.
    # Start the proxy with: python -m aicore.llm.providers.claude_code_proxy_server
    base_url: "http://localhost:8080"

    # Bearer token (the CLAUDE_PROXY_TOKEN printed at proxy startup).
    api_key: "your_proxy_token_here"

    # Claude model to use. The proxy forwards this to the Claude Code CLI.
    model: "claude-opus-4-5"

    # Optional: working directory for Claude Code on the proxy machine.
    # The proxy server must have this path in its --allowed-cwd-paths whitelist.
    cwd: "/path/to/project"

    # Optional: permission mode passed to ClaudeAgentOptions on the proxy.
    # Values: "bypassPermissions" (default), "acceptEdits", "default"
    permission_mode: "bypassPermissions"

    # Optional: maximum number of agentic turns before the session ends.
    max_turns: 10

    # Optional: list of tool names Claude is permitted to use.
    # Omit to allow all tools.
    allowed_tools:
      - "Bash"
      - "Read"
      - "Write"

    # Optional: set to true to skip the startup GET /health connectivity check.
    # Useful in production when the proxy server is known to be running.
    skip_health_check: false
  ```

---

## 7. Server Connectivity Validation on Init

- [x] Define `_check_server_health(self) -> None` as a method on `RemoteClaudeCodeLlm`.
- [x] Use `httpx.get(f"{self.config.base_url.rstrip('/')}/health", timeout=3.0)` (synchronous, since this runs inside a model_validator which is synchronous).
- [x] If the request succeeds (status 200), log at `DEBUG`: `"RemoteClaudeCodeLlm: proxy server health check passed ({base_url})"`.
- [x] If `httpx.ConnectError` or `httpx.ConnectTimeout` is raised, raise `ConnectionError`:
  ```
  Cannot connect to the Claude Code Proxy Server at {base_url}.
  Is it running? Start it with:
    python -m aicore.llm.providers.claude_code_proxy_server --port 8080
  See docs/claude_code_proxy_server_plan.md for setup instructions.
  To skip this check, set skip_health_check: true in your config.
  ```
- [x] If the response status is not 200, raise `RuntimeError(f"Proxy server at {base_url} returned unexpected status {response.status_code} on /health check.")`.
- [x] This check is guarded by `if not self.config.skip_health_check` in the model_validator.

---

## 8. Tests (`tests/test_remote_claude_code.py`)

### 8.1 SSE Deserialization Tests

- [x] `test_deserialize_stream_event`: Construct a `data` dict representing a `StreamEvent` with `content_block_delta` type and assert `_deserialize_message("stream_event", data)` returns a `StreamEvent` with the correct inner event dict.
- [x] `test_deserialize_assistant_message_text`: Feed a `data` dict with a single `TextBlock` content item and assert the returned `AssistantMessage` has one `TextBlock` with the correct text.
- [x] `test_deserialize_assistant_message_tool_use`: Feed a `data` dict with a `ToolUseBlock` content item and assert correct reconstruction of `name`, `id`, and `input`.
- [x] `test_deserialize_user_message_tool_result`: Feed a `data` dict with a `ToolResultBlock` and assert `tool_use_id` and `is_error` are preserved.
- [x] `test_deserialize_result_message`: Feed a full `ResultMessage` data dict including `session_id`, `total_cost_usd`, `usage`, and assert all fields are set.
- [x] `test_deserialize_error_event`: Assert that `_deserialize_message("error", {"message": "boom", "exit_code": 1})` raises `RuntimeError` with the message text included.
- [x] `test_deserialize_unknown_event_type`: Assert that an unrecognised event type returns `None` (does not raise).

### 8.2 HTTP Error Handling Tests

- [x] `test_iter_sse_401_raises_permission_error`: Mock `httpx.AsyncClient.stream` to return a response with status 401 and assert `PermissionError` is raised with a message mentioning the token.
- [x] `test_iter_sse_403_raises_permission_error`: Mock to return status 403 and assert `PermissionError` is raised with a message mentioning cwd whitelist.
- [x] `test_iter_sse_connection_refused`: Mock to raise `httpx.ConnectError` and assert `ConnectionError` is raised with a message mentioning the proxy server start command.
- [x] `test_iter_sse_500_raises_runtime_error`: Mock to return status 500 and assert `RuntimeError` is raised.

### 8.3 Request Body Construction Tests

- [x] `test_build_request_body_minimal`: Create a `RemoteClaudeCodeLlm` with only `base_url`, `api_key`, and `model` set (with health check skipped via `skip_health_check=True`). Assert that `_build_request_body("hello", None)` returns a dict with `prompt="hello"`, no `system_prompt` key, and `options["model"]` set.
- [x] `test_build_request_body_all_fields`: Set `permission_mode`, `cwd`, `max_turns`, and `allowed_tools` in config. Assert all appear in `options` and that `cli_path` does **not** appear even if set in config.
- [x] `test_build_request_body_excludes_cli_path`: Explicitly set `cli_path` in config and assert it is absent from the options dict.

### 8.4 Tool Callback Integration Tests

- [x] `test_tool_callback_fires_on_tool_use_block`: Mock the SSE stream to yield a sequence of events:
  1. `stream_event` with `content_block_start` containing a `tool_use` block.
  2. `user_message` with a `tool_result` block referencing the same `tool_use_id`.
  Assert that a registered `tool_callback` is called twice: once with `stage="started"` and once with `stage="concluded"`.

### 8.5 End-to-End `acomplete()` Tests (mocked SSE)

- [x] `test_acomplete_returns_text`: Mock `_iter_sse` to yield a pre-defined sequence of `(event_type, data_dict)` pairs that simulate a complete session (stream events with deltas, an `AssistantMessage`, and a `ResultMessage`). Assert that `acomplete("test prompt")` returns the expected text string.
- [x] `test_acomplete_records_usage`: Using the same mock, assert that `self.usage.record_completion` was called with non-zero token counts.
- [x] `test_acomplete_json_output`: Mock a stream that returns JSON text in the `AssistantMessage`. Assert that `acomplete("prompt", json_output=True)` returns a parsed Python dict.
- [x] `test_complete_sync_wrapper`: Assert that `complete("prompt")` (the sync wrapper) produces the same result as `await acomplete("prompt")` using `asyncio.run`. Use the same SSE mock.

### 8.6 Health Check Tests

- [x] `test_health_check_skipped_when_flag_set`: Assert that creating a `RemoteClaudeCodeLlm` with `skip_health_check=True` does **not** make any HTTP call (mock `httpx.get` and assert it was not called).
- [x] `test_health_check_raises_on_connect_error`: Mock `httpx.get` to raise `httpx.ConnectError`. Assert `ConnectionError` is raised during `RemoteClaudeCodeLlm` instantiation.
- [x] `test_health_check_passes_silently`: Mock `httpx.get` to return a 200 response. Assert `RemoteClaudeCodeLlm` is created without error.

---

## 9. Implementation Order (Suggested)

Implement in this order to avoid circular dependencies and to allow incremental testing at each step:

- [x] **Step 1:** Refactor `claude_code.py` — create `ClaudeCodeBase`, extract `_process_message()`, make `ClaudeCodeLlm` a subclass. Run existing tests to confirm no regression.
- [x] **Step 2:** Update `aicore/llm/config.py` — add `"remote_claude_code"` to the provider Literal and add `skip_health_check` field.
- [x] **Step 3:** Update `aicore/models_metadata.json` — add `remote_claude_code-*` entries.
- [x] **Step 4:** Write `aicore/llm/providers/remote_claude_code.py` — class definition, validators, `_build_request_body`, `_iter_sse`, `_deserialize_message`, `acomplete`, `complete`, `_check_server_health`.
- [x] **Step 5:** Register the provider in `__init__.py` and `llm.py`.
- [x] **Step 6:** Write `config/config_example_remote_claude_code.yml`.
- [x] **Step 7:** Write `tests/test_remote_claude_code.py` — all tests in section 8.
- [ ] **Step 8:** Integration test: start the proxy server locally and run a real `acomplete()` call through the remote provider end-to-end.

---

## 10. Known Limitations and Future Work (document in code comments)

- [x] The `complete()` synchronous wrapper uses `asyncio.run()`, which creates a new event loop. Callers already inside an async context must use `acomplete()`. Document this with the same warning string used in `ClaudeCodeLlm`.
- [x] SSE reconnection (using the `Last-Event-ID` header) is not implemented on the client side. The `_last_sse_id` attribute is tracked but not used for reconnection. This is a known gap; a future version could auto-retry interrupted streams.
- [x] `ThinkingBlock` reconstruction in `_deserialize_message` depends on the version of `claude-agent-sdk` installed. If the type does not exist, catch `ImportError` and log a debug warning, then fall back to treating it as a `TextBlock`.
- [x] The provider does not implement `_build_mcp_servers()` or `connect_to_mcp()` beyond the inherited no-ops because MCP server configuration is passed as part of the proxy server's startup config, not the per-request options.
- [x] Streaming text is received from the proxy server's SSE frames. There is no way to implement true per-token backpressure over HTTP SSE; the proxy buffers and forwards frames as the SDK emits them.
