
# Claude Code Provider

The Claude Code provider lets you route AiCore completions through your **Claude subscription** via the [Claude Agents Python SDK](https://platform.claude.com/docs/en/agent-sdk/python) — no Anthropic API key required. It ships as two complementary providers:

| Provider | Use case |
|---|---|
| [`claude_code`](#local-provider-claude-code) | Runs the CLI **locally** on the same machine as AiCore |
| [`remote_claude_code`](#remote-provider-remote-claude-code) | Connects to a [`aicore-proxy-server`](#proxy-server) running elsewhere over HTTP |

Both share the same `acomplete()` / `complete()` interface and emit identical tool-call streaming events.

---

## Local Provider (`claude_code`)

### Prerequisites

```bash
# 1. Node.js 18+ and the Claude Code CLI
npm install -g @anthropic-ai/claude-code

# 2. Authenticate once
claude login

# 3. Install AiCore
pip install core-for-ai
```

### Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="claude_code",
    model="claude-sonnet-4-5-20250929",
    # No api_key needed — auth is handled by the CLI
)
```

YAML equivalent:

```yaml
llm:
  provider: "claude_code"
  model: "claude-sonnet-4-5-20250929"

  # Optional
  permission_mode: "bypassPermissions"   # default — all tools allowed
  cwd: "/path/to/your/project"
  max_turns: 10
  mcp_config: "./mcp_config.json"
  cli_path: "/usr/local/bin/claude"      # override if not on PATH
  allowed_tools:
    - "Read"
    - "Write"
    - "Bash"
```

### Config Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | string | — | `"claude_code"` |
| `model` | string | — | Claude model name |
| `permission_mode` | string | `"bypassPermissions"` | `"bypassPermissions"`, `"acceptEdits"`, `"default"`, `"plan"` |
| `cwd` | string | `None` | Working directory for the CLI |
| `max_turns` | int | `None` | Max agentic turns before session ends |
| `allowed_tools` | list[str] | `None` | Tool names Claude may use (all allowed if omitted) |
| `cli_path` | string | `None` | Absolute path to the `claude` binary |
| `mcp_config` | string | `None` | Path to an MCP config JSON file |

> `api_key`, `temperature`, and `max_tokens` are silently ignored — the CLI controls model parameters internally.

### Basic Usage

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

llm = Llm.from_config(LlmConfig(
    provider="claude_code",
    model="claude-sonnet-4-5-20250929",
))

# Sync
response = llm.complete("List all Python files in this project")
print(response)

# Async
response = await llm.acomplete("List all Python files in this project")
print(response)
```

### Tool Call Callbacks

```python
def on_tool_event(event: dict):
    if event["stage"] == "started":
        print(f"→ Calling tool: {event['tool_name']}")
    elif event["stage"] == "concluded":
        status = "✗" if event["is_error"] else "✓"
        print(f"{status} Tool finished: {event['tool_name']}")

llm.tool_callback = on_tool_event
response = await llm.acomplete("Find all TODO comments in the codebase")
```

`TOOL_CALL_START_TOKEN` and `TOOL_CALL_END_TOKEN` are also emitted through `stream_handler`, so existing stream consumers work without changes.

---

## Proxy Server (`aicore-proxy-server`)

The proxy server wraps `claude-agent-sdk` as a FastAPI SSE service so Claude Code can be shared over HTTP. Use it when:

- The CLI is authenticated on a **different machine** (dev box, server, WSL)
- You want to **share one Claude subscription** across multiple AiCore clients
- Your AiCore workload runs in a **container or cloud** that can't run the CLI

### Installation (server-side only)

```bash
pip install core-for-ai[claude-server]
npm install -g @anthropic-ai/claude-code
claude login
```

The `[claude-server]` extra installs `fastapi`, `uvicorn[standard]`, and `python-dotenv`. `pyngrok` is optional and only needed for `--tunnel ngrok`.

### Starting the Server

```bash
# Minimal — prompts for tunnel choice interactively
aicore-proxy-server

# Fully configured
aicore-proxy-server \
  --host 0.0.0.0 \
  --port 8080 \
  --token my-secret-token \
  --tunnel none \
  --cwd /path/to/project

# Via Python module
python -m aicore.scripts.claude_code_proxy_server --port 8080 --tunnel none
```

The bearer token is printed at startup. To reuse it across restarts:

```bash
echo 'CLAUDE_PROXY_TOKEN=your_token' >> .env
```

### CLI Options

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address (`0.0.0.0` for LAN) |
| `--port` | `8080` | TCP port |
| `--token` | *(auto-generated)* | Bearer token; also reads `CLAUDE_PROXY_TOKEN` |
| `--tunnel` | *(prompt)* | `none` / `ngrok` / `cloudflare` / `ssh` |
| `--tunnel-port` | same as `--port` | Remote port for SSH tunnels |
| `--cwd` | *(unrestricted)* | Force working directory for all sessions |
| `--allowed-cwd-paths` | *(any)* | Whitelist of `cwd` values clients may request |
| `--log-level` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `--cors-origins` | `*` | Allowed CORS origins |

### Tunnel Modes

| Mode | Requirement | Notes |
|---|---|---|
| `none` | — | Local network only |
| `ngrok` | `pip install pyngrok` | Auth token stored in OS credential store on first run, loaded automatically thereafter |
| `cloudflare` | `cloudflared` on PATH | Quick tunnel, ephemeral URL |
| `ssh` | VPS with SSH | Prints the `ssh -R` command; no extra software needed |

### API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Status, uptime, CLI version, active streams |
| `GET` | `/capabilities` | Bearer | Supported options and server defaults |
| `POST` | `/query` | Bearer | Stream a query as SSE |
| `DELETE` | `/query/{id}` | Bearer | *(501 stub — future WebSocket cancellation)* |

---

## Remote Provider (`remote_claude_code`)

### Prerequisites (client-side only)

```bash
pip install core-for-ai   # no CLI or server extras needed
```

The proxy server must be running and reachable. A `GET /health` check is performed at startup (disable with `skip_health_check: true`).

### Configuration

```python
from aicore.llm.config import LlmConfig

config = LlmConfig(
    provider="remote_claude_code",
    model="claude-sonnet-4-5-20250929",
    base_url="http://your-proxy-host:8080",
    api_key="your_proxy_token",           # CLAUDE_PROXY_TOKEN from server startup
)
```

YAML equivalent:

```yaml
llm:
  provider: "remote_claude_code"
  model: "claude-sonnet-4-5-20250929"
  base_url: "http://your-proxy-host:8080"   # or a tunnel URL
  api_key: "your_proxy_token"

  # Optional — forwarded to the proxy
  permission_mode: "bypassPermissions"
  cwd: "/path/to/project"                   # must be in --allowed-cwd-paths
  max_turns: 10
  allowed_tools:
    - "Bash"
    - "Read"
    - "Write"
  skip_health_check: false
```

### Config Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | string | — | `"remote_claude_code"` |
| `model` | string | — | Claude model name |
| `base_url` | string | — | **Required.** Proxy server URL |
| `api_key` | string | — | **Required.** `CLAUDE_PROXY_TOKEN` from server |
| `permission_mode` | string | `None` | Forwarded to proxy |
| `cwd` | string | `None` | Forwarded to proxy |
| `max_turns` | int | `None` | Forwarded to proxy |
| `allowed_tools` | list[str] | `None` | Forwarded to proxy |
| `skip_health_check` | bool | `false` | Skip startup `/health` check |

### Basic Usage

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

llm = Llm.from_config(LlmConfig(
    provider="remote_claude_code",
    model="claude-sonnet-4-5-20250929",
    base_url="http://your-proxy-host:8080",
    api_key="your_proxy_token",
))

response = await llm.acomplete("Summarise this codebase")
print(response)
```

---

## Supported Models

| Model | Max Tokens | Context Window |
|---|---|---|
| `claude-sonnet-4-5-20250929` | 64 000 | 200 000 |
| `claude-opus-4-6` | 32 000 | 200 000 |
| `claude-haiku-4-5-20251001` | 64 000 | 200 000 |
| `claude-3-7-sonnet-latest` | 64 000 | 200 000 |
| `claude-3-5-sonnet-latest` | 8 192 | 200 000 |

---

## Related

- [LLM Overview](../llm/overview.md)
- [LLM Configuration](../config/llmconfig.md)
- [Claude Code Quickstart](../quickstart/claude-code.md)
- [MCP Integration](../llm/mcp.md)
