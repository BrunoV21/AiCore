
### 🖥️ Claude Code Provider — Local & Remote

AiCore now ships full support for routing completions through your **Claude subscription** via the [Claude Agents Python SDK](https://platform.claude.com/docs/en/agent-sdk/python) — no Anthropic API key required.

Two new providers are available:

**`claude_code`** — runs the Claude Code CLI directly on the same machine as AiCore:

```yaml
llm:
  provider: "claude_code"
  model: "claude-sonnet-4-5-20250929"
```

Prerequisites: `npm install -g @anthropic-ai/claude-code` and `claude login`.

---

**`remote_claude_code`** — connects over HTTP SSE to a new **Claude Code Proxy Server**, allowing the CLI to live on a different machine (server, WSL, shared dev box):

```yaml
llm:
  provider: "remote_claude_code"
  model: "claude-sonnet-4-5-20250929"
  base_url: "http://your-proxy-host:8080"
  api_key: "your_proxy_token"
```

---

**`aicore-proxy-server`** — a new FastAPI SSE service that wraps `claude-agent-sdk` and exposes it over HTTP with Bearer token authentication. Install and start it with:

```bash
pip install core-for-ai[claude-server]
aicore-proxy-server --port 8080 --tunnel none
```

Supports `ngrok`, `cloudflare`, and `ssh` tunnels for remote access. The `ngrok` auth token is stored securely in the OS credential store (Windows Credential Manager / macOS Keychain / Linux Secret Service) on first use and loaded automatically on subsequent runs.

Both providers share the same `acomplete()` / `complete()` interface and emit identical tool-call streaming events via `stream_handler` and `tool_callback`.

→ [Full documentation](../providers/claude-code.md)
→ [Quickstart guide](../quickstart/claude-code.md)
→ [LLM system internals](../llm/claude-code.md)
