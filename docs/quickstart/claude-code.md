
# Claude Code Quickstart

AiCore's Claude Code providers let you use your **Claude subscription** directly — no Anthropic API key needed. This guide gets you from zero to a working completion in a few minutes.

Choose your path:

| Path | When to use |
|---|---|
| [Local](#local-setup) | The Claude Code CLI can run on the same machine as your AiCore code |
| [Remote](#remote-setup) | AiCore runs in a container, cloud, or a machine without the CLI |

---

## Local Setup

### 1. Install the Claude Code CLI

```bash
# Requires Node.js 18+
npm install -g @anthropic-ai/claude-code
```

### 2. Authenticate

```bash
claude login
```

Follow the browser prompt to authorise with your Claude account.

### 3. Install AiCore

```bash
pip install core-for-ai
```

### 4. Make your first request

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

llm = Llm.from_config(LlmConfig(
    provider="claude_code",
    model="claude-sonnet-4-5-20250929",
))

response = llm.complete("Say hello!")
print(response)
```

Or with a YAML config file:

```yaml
# config.yml
llm:
  provider: "claude_code"
  model: "claude-sonnet-4-5-20250929"
```

```python
from aicore.config import Config
from aicore.llm import Llm

config = Config.from_yaml("./config.yml")
llm = Llm.from_config(config.llm)
print(llm.complete("Say hello!"))
```

---

## Remote Setup

Use this path when the CLI lives on a different machine (server, WSL, shared dev box) and you want to reach it over HTTP.

### Step 1 — Set up the proxy server (server machine)

```bash
pip install core-for-ai[claude-server]
npm install -g @anthropic-ai/claude-code
claude login
```

Start the server:

```bash
aicore-proxy-server --host 0.0.0.0 --port 8080 --tunnel none
```

The server prints a **bearer token** (`CLAUDE_PROXY_TOKEN`) at startup. Copy it — you'll need it on the client side.

To persist the token across restarts:

```bash
echo 'CLAUDE_PROXY_TOKEN=your_token_here' >> .env
```

### Step 2 — Install AiCore on the client machine

```bash
pip install core-for-ai   # no extras needed
```

### Step 3 — Make your first remote request

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

llm = Llm.from_config(LlmConfig(
    provider="remote_claude_code",
    model="claude-sonnet-4-5-20250929",
    base_url="http://server-ip:8080",
    api_key="your_proxy_token",
))

response = llm.complete("Say hello!")
print(response)
```

Or with a YAML config:

```yaml
# config.yml
llm:
  provider: "remote_claude_code"
  model: "claude-sonnet-4-5-20250929"
  base_url: "http://server-ip:8080"
  api_key: "your_proxy_token"
```

---

## Expose the proxy server over the internet (optional)

If the client and server are on different networks, start the server with a tunnel:

```bash
# ngrok (auth token stored securely in OS credential store on first run)
aicore-proxy-server --port 8080 --tunnel ngrok

# Cloudflare quick tunnel (cloudflared must be on PATH)
aicore-proxy-server --port 8080 --tunnel cloudflare

# SSH reverse tunnel (prints the ssh -R command for your own VPS)
aicore-proxy-server --port 8080 --tunnel ssh
```

Use the printed tunnel URL as `base_url` in the client config.

---

## Next Steps

- [Full Claude Code provider reference](../providers/claude-code.md)
- [All config options](../config/llmconfig.md)
- [Tool call callbacks & streaming](../providers/claude-code.md#tool-call-callbacks)
- [MCP integration](../llm/mcp.md)
