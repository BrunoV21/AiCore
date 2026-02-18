# Claude Code Provider — Implementation Checklist

> **SDK choice: `query()`** — stateless, fresh session per call, internal tool chaining via `max_turns`. Matches AiCore's stateless design.

---

## 1. Config (`aicore/llm/config.py`)

- [ ] Add `"claude_code"` to the `provider` `Literal` type
- [ ] Add optional field `permission_mode: Optional[str]`
- [ ] Add optional field `cwd: Optional[str]`
- [ ] Add optional field `max_turns: Optional[int]`
- [ ] Add optional field `allowed_tools: Optional[List[str]]`
- [ ] Add optional field `cli_path: Optional[str]`
- [ ] Document that `temperature` and `max_tokens` are ignored for this provider

---

## 2. Models metadata (`aicore/models_metadata.py`)

- [ ] Add entries for Claude Code-accessible models (sonnet, opus, haiku variants)
- [ ] Set `tool_use = True` for all entries
- [ ] Set `pricing = None` for all entries (cost comes from `ResultMessage.total_cost_usd`)

---

## 3. Provider (`aicore/llm/providers/claude_code.py`)

### Setup
- [ ] Create `ClaudeCodeLlm(LlmBaseProvider)` class
- [ ] Add `model_validator` that checks `claude-agent-sdk` is installed
- [ ] Add CLI presence check via `shutil.which("claude")` — raise `CLINotFoundError` with install instructions if missing
- [ ] Override `validate_config()` as a no-op (auth is handled by the CLI, not an API key)
- [ ] Override `use_as_reasoner()` to raise `NotImplementedError` (not applicable to this provider)
- [ ] Set a tiktoken fallback as `tokenizer_fn`

### MCP bridge — `_build_mcp_servers()`
- [ ] If `mcp_config` is set, pass the path directly to `ClaudeAgentOptions.mcp_servers`
- [ ] If `self.tools` is populated (ToolSchema list), wrap each tool into an in-process `create_sdk_mcp_server` that proxies calls to `self.mcp.servers.call_tool()`
- [ ] Build the `allowed_tools` list from tool names using the correct `mcp__<server>__<tool>` prefix

### Options builder — `_build_options()`
- [ ] Map all relevant `LlmConfig` fields to `ClaudeAgentOptions` fields
- [ ] Always set `include_partial_messages=True` to enable `StreamEvent` for streaming

### Prompt serialisation — `_to_prompt_string()`
- [ ] Handle `str` input
- [ ] Handle `BaseModel` / `RootModel` input via `model_to_str()`
- [ ] Handle `List[str | dict | ToolCallSchema]` input — flatten to a single string with role prefixes

### Stream delta extraction — `_extract_stream_delta()`
- [ ] Extract text from `StreamEvent.event` where `type == "content_block_delta"` and `delta.type == "text_delta"`

### Text and usage extraction — `_extract_text_and_usage()`
- [ ] Collect `TextBlock` text from all `AssistantMessage` objects in the message list
- [ ] Read `input_tokens`, `output_tokens` from `ResultMessage.usage`
- [ ] Read `cost` from `ResultMessage.total_cost_usd`

### `acomplete()` override
- [ ] Override `acomplete()` with the same signature as the base class
- [ ] Log a warning and ignore `prefix_prompt` if passed (not supported by `query()`)
- [ ] Log a warning and ignore `img_path` if passed (not supported in initial version)
- [ ] Call `connect_to_mcp()` before building options
- [ ] Build prompt string, MCP servers, and options
- [ ] Iterate `query()` messages; pipe `StreamEvent` deltas to `stream_handler` when `stream=True`
- [ ] Emit `STREAM_START_TOKEN` / `STREAM_END_TOKEN` via `stream_handler`
- [ ] Call `_extract_text_and_usage()` after iteration completes
- [ ] Record usage via `self.usage.record_completion()` using `ResultMessage.session_id` as `completion_id`
- [ ] Apply `extract_json()` when `json_output=True`
- [ ] Build synthetic `completion_args` dict and call `collector.arecord_completion()` in `finally`
- [ ] Handle `as_message_records` return format
- [ ] Catch `CLINotFoundError`, `CLIConnectionError`, `ProcessError` and re-raise with `error_message` set

### `complete()` override
- [ ] Override `complete()` as a synchronous wrapper around `acomplete()` using `asyncio.run()`
- [ ] Document that callers inside an existing event loop must use `acomplete()` directly

---

## 4. Provider factory (`aicore/llm/llm.py`)

- [ ] Add `CLAUDE_CODE` entry to the `Providers` enum mapping `"claude_code"` → `ClaudeCodeLlm`

---

## 5. Registration (`aicore/llm/providers/__init__.py`)

- [ ] Import and export `ClaudeCodeLlm`

---

## 6. Example config (`config/`)

- [ ] Add `config_example_claude_code.yml` following the pattern of other example configs

---

## 7. Tests (`tests/test_llm.py`)

- [ ] Add `claude_code` fixture to the provider config fixtures
- [ ] Include `claude_code` in the parametrized `complete()` test
- [ ] Include `claude_code` in the parametrized JSON output test
- [ ] Add a dedicated test for unsupported parameter warnings (`prefix_prompt`, `img_path`)
- [ ] Add a test verifying `CLINotFoundError` is raised when the CLI is not on PATH

---

## 8. Dependencies (`setup.py` / `pyproject.toml`)

- [ ] Add `claude-agent-sdk` to install requirements
- [ ] Add a note in the project README that the Claude Code CLI must be installed separately (`npm install -g @anthropic-ai/claude-code`)
