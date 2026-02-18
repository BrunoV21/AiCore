# Claude Code Proxy Server — Implementation Checklist

> **Purpose:** A standalone Python script that runs on a developer's local machine. It interactively guides the user through any missing prerequisites at startup, then serves a FastAPI SSE endpoint that proxies `claude_agent_sdk.query()` calls. The server prints clear status output so the operator knows it is running and where to point their client.
>
> **Entry point:** `python -m aicore.llm.providers.claude_code_proxy_server`
> **File location:** `aicore/llm/providers/claude_code_proxy_server.py`

---

## 1. Package and Dependencies

- [x] Declare all required runtime packages in a comment block at the top of the file so the user knows what to install:
  - `fastapi` — ASGI web framework
  - `uvicorn[standard]` — ASGI server with WebSocket and HTTP/2 support
  - `httpx` — async HTTP client (used by the SSE client side in tests and for health self-checks)
  - `python-dotenv` — load `.env` file at startup so the user can persist `CLAUDE_PROXY_TOKEN` there
  - `pydantic` — request/response models (already a project dependency)
  - `claude-agent-sdk` — the SDK that wraps the Claude Code CLI; install docs at https://platform.claude.com/docs/en/agent-sdk/python
  - `pyngrok` (optional) — Python wrapper for ngrok tunnels; only required when `--tunnel ngrok` is passed
- [x] Do **not** add these to `setup.py` or `pyproject.toml` as hard dependencies — they are only needed if the user runs the proxy server script directly. Print a clear pip install one-liner for any missing optional package instead of crashing silently.
- [x] The script must remain runnable as a **standalone file** (`python claude_code_proxy_server.py`) in addition to being invocable as a module (`python -m aicore.llm.providers.claude_code_proxy_server`). Ensure the `if __name__ == "__main__":` block handles both cases identically.
- [x] Guard all optional imports (`pyngrok`, `dotenv`) inside `try/except ImportError` blocks with helpful messages rather than module-level unconditional imports.

---

## 2. CLI Arguments (argparse)

- [x] Parse arguments with `argparse.ArgumentParser` in a `parse_args()` function called from `main()`.
- [x] `--port` (int, default `8080`) — TCP port the local server listens on.
- [x] `--host` (str, default `"127.0.0.1"`) — bind address; user should pass `0.0.0.0` when LAN access is desired.
- [x] `--token` (str, default `None`) — override the auto-generated proxy token; takes precedence over the `CLAUDE_PROXY_TOKEN` env var.
- [x] `--tunnel` (str, choices `["ngrok", "cloudflare", "ssh", "none"]`, default `"none"`) — which tunnel method to activate.
- [x] `--cwd` (str, default `None`) — working directory that Claude Code CLI will use for all requests; if omitted the server does not impose a cwd and requests may specify their own.
- [x] `--allowed-cwd-paths` (str, nargs `"*"`, default `[]`) — whitelist of absolute paths that clients are permitted to request as `cwd`. If non-empty, any request whose `cwd` is not a sub-path of one of these roots is rejected with HTTP 403.
- [x] `--log-level` (str, choices `["DEBUG", "INFO", "WARNING", "ERROR"]`, default `"INFO"`) — passed directly to `logging.basicConfig`.
- [x] `--cors-origins` (str, nargs `"*"`, default `["*"]`) — CORS allowed origins; useful if the caller is a browser-based client.
- [x] `--tunnel-port` (int, default `None`) — remote port to use for SSH reverse tunnels; defaults to `--port` value if not set.

---

## 3. Startup Checks and User Guidance

Run all checks sequentially before `uvicorn` is started. Print a numbered progress list so the user can follow along. Abort with a non-zero exit code only on hard failures (missing SDK, missing CLI); print warnings for soft issues (missing tunnel auth token).

### 3.1 Python Version

- [x] Check `sys.version_info >= (3, 11)` and abort with a clear message if the check fails:
  ```
  ERROR: Python 3.11+ is required. You are running Python {sys.version}. Please upgrade.
  ```

### 3.2 `claude-agent-sdk` Installation Check

- [x] Attempt `import claude_agent_sdk` inside a `try/except ImportError` block.
- [x] If missing, print:
  ```
  ERROR: claude-agent-sdk is not installed.
  Install it with: pip install claude-agent-sdk
  Docs: https://platform.claude.com/docs/en/agent-sdk/python
  ```
  Then call `sys.exit(1)`.

### 3.3 Claude CLI on PATH

- [x] Call `shutil.which("claude")` to check for the CLI binary.
- [x] If not found and `--cwd` was not given as a custom `cli_path`, print:
  ```
  ERROR: The 'claude' CLI is not on your PATH.
  Install it with: npm install -g @anthropic-ai/claude-code
  Docs: https://docs.anthropic.com/en/docs/claude-code/getting-started
  ```
  Then call `sys.exit(1)`.
- [x] If a `--cli-path` override is provided (future extension), check that the path exists instead.

### 3.4 Claude CLI Authentication Check

- [x] Run `subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)`.
- [x] Cache the version string from stdout for later use in the `/health` endpoint response.
- [x] If the process exits with a non-zero code **or** if stdout/stderr contains strings like `"not logged in"`, `"auth"`, `"login"`, or `"token"` (case-insensitive), print:
  ```
  WARNING: Claude CLI may not be authenticated. Run 'claude login' and then retry.
  If you are already authenticated, this warning can be ignored.
  ```
  Do not abort on this warning — the server may still work if auth is handled via environment variables.

### 3.5 Proxy Token — Load or Generate

- [x] Call `load_dotenv()` (if `python-dotenv` is installed) to populate env from a `.env` file in the current directory before reading the env var.
- [x] Read `CLAUDE_PROXY_TOKEN` from `os.environ`.
- [x] If `--token` CLI arg was supplied, use it and skip generation entirely.
- [x] If neither CLI arg nor env var is set, generate a cryptographically secure token with `secrets.token_urlsafe(32)` and store it in a module-level variable `PROXY_TOKEN`.
- [x] When a token is **generated** (not supplied), print a prominent notice:
  ```
  ============================================================
  GENERATED PROXY TOKEN (ephemeral — not saved automatically)
  Token: <full token here>

  To persist this token across restarts, add it to your .env file:
    echo 'CLAUDE_PROXY_TOKEN=<token>' >> .env
  Or pass it at startup:
    python -m aicore.llm.providers.claude_code_proxy_server --token <token>
  ============================================================
  ```
- [x] When a token is **loaded from env or CLI**, print a short confirmation: `  [OK] Proxy token loaded (set via {'CLI arg' | 'CLAUDE_PROXY_TOKEN env var'})`.

### 3.6 Pre-start Configuration Summary

- [x] After all checks pass, print a formatted table:
  ```
  ┌─ Configuration ──────────────────────────────────┐
  │ Port           : 8080                            │
  │ Host           : 127.0.0.1                       │
  │ CWD            : /path/to/cwd  (or "unrestricted") │
  │ Allowed CWDs   : [list] (or "any")               │
  │ Tunnel         : none / ngrok / cloudflare / ssh  │
  │ Log level      : INFO                            │
  │ Claude version : claude 1.x.x                   │
  └───────────────────────────────────────────────────┘
  ```

---

## 4. Tunnel Setup (conditional on `--tunnel` argument)

### 4a. ngrok Tunnel

- [x] Only execute this section when `--tunnel ngrok` is passed.
- [x] Check if `pyngrok` is importable; if not, print:
  ```
  ERROR: pyngrok is required for ngrok tunnels.
  Install it with: pip install pyngrok
  ```
  Then `sys.exit(1)`.
- [x] Check `NGROK_AUTH_TOKEN` in `os.environ`. If missing, print:
  ```
  WARNING: NGROK_AUTH_TOKEN is not set. Free ngrok tunnels work without a token but
  have session limits. Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken
  Set it with: export NGROK_AUTH_TOKEN=<your_token>
  ```
- [x] Call `pyngrok.ngrok.connect(port, proto="http")` and capture the returned `NgrokTunnel` object.
- [x] Extract `tunnel.public_url` and store it as `TUNNEL_URL`.
- [x] Print the public URL prominently.
- [x] Print a note: `NOTE: Free ngrok URLs are ephemeral and change on every restart.`

### 4b. Cloudflare Tunnel

- [x] Only execute this section when `--tunnel cloudflare` is passed.
- [x] Check `shutil.which("cloudflared")`. If not found, print:
  ```
  ERROR: 'cloudflared' binary not found on PATH.
  Download it from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
  ```
  Then `sys.exit(1)`.
- [x] **Quick-tunnel mode** (default, no CF account required): Launch `subprocess.Popen(["cloudflared", "tunnel", "--url", f"http://localhost:{port}"], stderr=subprocess.PIPE, text=True)` and read stderr lines until a line containing `trycloudflare.com` is found. Extract the URL from that line using a regex pattern `r'https://[a-z0-9-]+\.trycloudflare\.com'`.
- [x] Store the extracted URL as `TUNNEL_URL` and print it.
- [x] Keep the `cloudflared` process alive in the background (do not wait for it); register `process.terminate()` in the shutdown handler.
- [x] Print a note:
  ```
  NOTE: Quick tunnels are ephemeral. For a stable URL, use a named tunnel
  (requires a Cloudflare account): https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
  ```

### 4c. SSH / VPS Reverse Tunnel

- [x] Only execute this section when `--tunnel ssh` is passed.
- [x] Do not attempt to spawn or verify any SSH process — the user manages this externally.
- [x] Print the SSH command template:
  ```
  Run the following command on your local machine to expose the proxy server:

    ssh -R {remote_port}:localhost:{local_port} user@your-vps -N

  Replace 'user@your-vps' with your VPS credentials and remote_port with the desired remote port.
  Ensure 'GatewayPorts yes' is set in /etc/ssh/sshd_config on your VPS and that sshd was reloaded.

  The proxy server will then be reachable at:
    http://your-vps-ip:{remote_port}
  ```
  Where `{local_port}` is `--port` and `{remote_port}` is `--tunnel-port` (defaults to `--port`).
- [x] Set `TUNNEL_URL = None` — the server cannot know the public URL automatically for SSH tunnels.

### 4d. No Tunnel (local only)

- [x] When `--tunnel none` (the default), collect all LAN IP addresses of the machine using `socket.getaddrinfo(socket.gethostname(), None)` filtered for IPv4 addresses, or fall back to `socket.gethostbyname(socket.gethostname())`.
- [x] Print:
  ```
  NOTE: Server is only accessible on the local network (no tunnel configured).
  LAN addresses:
    http://192.168.x.x:{port}
    http://127.0.0.1:{port}
  ```

---

## 5. FastAPI Application Structure

- [x] Create a single module-level `app = FastAPI(title="Claude Code Proxy Server", version="1.0.0")` instance.
- [x] Add `CORSMiddleware` with `allow_origins=args.cors_origins`, `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True`. Note in a comment that this defaults to `["*"]` because the proxy is a developer tool and is not intended to be exposed publicly without a proper token.
- [x] Define a module-level `active_streams: int = 0` counter. Use a `threading.Lock` or `asyncio.Lock` to increment/decrement it safely from async context.
- [x] Track `SERVER_START_TIME = time.time()` at startup for the uptime field in `/health`.
- [x] Add a request logging middleware (`@app.middleware("http")`) that logs: request method, path, client host, and response status code at `INFO` level using Python's `logging` module.
- [x] Add a lifespan shutdown handler (via `@app.on_event("shutdown")` or the `lifespan` context manager) that prints: `Claude Code Proxy Server shutting down. Goodbye.` and terminates any tunnel subprocess.

### 5.1 Bearer Token Auth Dependency

- [x] Define `async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()))` using `fastapi.security.HTTPBearer`.
- [x] Compare `credentials.credentials` against the module-level `PROXY_TOKEN` using `hmac.compare_digest` to prevent timing attacks.
- [x] Raise `HTTPException(status_code=401, detail="Invalid or missing Bearer token")` if the comparison fails.
- [x] Apply this dependency to all endpoints except `GET /health`.

---

## 6. Endpoints

### 6.1 GET /health

- [x] No authentication required.
- [x] Define a `HealthResponse(BaseModel)` Pydantic model with fields:
  - `status: str` — always `"ok"`
  - `server_version: str` — hardcoded semantic version string of this script (e.g. `"1.0.0"`)
  - `claude_cli_version: str` — the cached version string captured during the startup check in section 3.4; `"unknown"` if the check failed
  - `uptime_seconds: float` — `time.time() - SERVER_START_TIME`
  - `active_streams: int` — current value of the `active_streams` counter
  - `authenticated: bool` — always `True` (the fact that the server is running means auth was set up; the field is informational for monitoring)
- [x] Return a `HealthResponse` instance. FastAPI will serialise it as JSON automatically.

### 6.2 GET /capabilities

- [x] Require Bearer token auth via the dependency defined in section 5.1.
- [x] Define a `CapabilitiesResponse(BaseModel)` Pydantic model with fields:
  - `server_version: str`
  - `sdk_version: str` — obtain from `importlib.metadata.version("claude-agent-sdk")` or `"unknown"` if unavailable
  - `supported_options: list[str]` — list of the `ClaudeAgentOptions` field names the server will forward from the request body (e.g. `["model", "permission_mode", "cwd", "max_turns", "allowed_tools", "system_prompt"]`)
  - `server_enforced_defaults: dict` — any option overrides the server always applies, e.g. `{"include_partial_messages": True}` and, if `--cwd` was set at startup, `{"cwd": "<configured_cwd>"}`
  - `cwd_whitelist: list[str]` — the value of `--allowed-cwd-paths`; empty list means unrestricted
- [x] Return a `CapabilitiesResponse` instance.

### 6.3 POST /query

- [x] Require Bearer token auth.
- [x] Define a `QueryRequest(BaseModel)` Pydantic model with fields:
  - `prompt: str` — the user prompt (required)
  - `system_prompt: Optional[str] = None`
  - `options: Optional[dict] = {}` — arbitrary `ClaudeAgentOptions` fields the client wants to pass; the server merges these with its own defaults/overrides
- [x] **Server-side CWD enforcement:** If `--allowed-cwd-paths` is non-empty:
  - Read `requested_cwd = options.get("cwd")`.
  - If `requested_cwd` is set, check that `Path(requested_cwd).resolve()` starts with one of the allowed roots.
  - If the check fails, raise `HTTPException(status_code=403, detail=f"Requested cwd '{requested_cwd}' is not within the allowed paths: {allowed_cwd_paths}")`.
- [x] **Option merging:** Merge options in this priority order (highest wins): server startup config (`--cwd`) overrides request options overrides server defaults. Always force `include_partial_messages=True` regardless of what the client sends.
- [x] **Unset proxy-related environment variables:** Use the `_unset_env("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")` context manager (imported from or duplicated from `claude_code.py`) so that the subprocess does not inherit variables that might interfere with the CLI.
- [x] **Build `ClaudeAgentOptions`:** Construct the options object from the merged dict. Wrap in a try/except to catch validation errors and return HTTP 422 with a clear message.
- [x] **Increment `active_streams`** before starting the generator; **decrement** in a `finally` block inside the generator.
- [x] **Return a `StreamingResponse`** with:
  - `media_type="text/event-stream"`
  - Headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no` (prevents nginx from buffering SSE)
- [x] **SSE generator function** (`async_generator`):
  - Maintain a module-level or closure-scoped monotonically increasing `_sse_id` counter.
  - For each message yielded by `claude_agent_sdk.query(prompt=prompt_str, options=options)`:
    - Determine the event type string from the message type (see section 7).
    - Serialise the message to a dict using `dataclasses.asdict()` or the custom JSON encoder (see section 7).
    - Yield an SSE frame:
      ```
      id: {_sse_id}\n
      event: {event_type}\n
      data: {json_string}\n
      \n
      ```
    - Increment `_sse_id` by 1.
  - On any exception during streaming: yield a final `error` event frame containing `{"message": str(e), "exit_code": getattr(e, "exit_code", None)}`, then return.
  - In the `finally` block: log completion metrics (session_id, cost, turns, duration_ms) and decrement `active_streams`.
- [x] Log at `INFO` level when a `/query` request starts: client IP, model requested (from options), prompt length in characters, and a summary of the effective options.
- [x] Log at `INFO` level when a `/query` stream completes: session_id (extracted from `ResultMessage`), total_cost_usd, num_turns (count of `AssistantMessage` instances), duration_ms.

### 6.4 DELETE /query/{session_id} (stub only)

- [x] Require Bearer token auth.
- [x] Accept `session_id: str` as a path parameter.
- [x] Return `HTTPException(status_code=501, detail="Stream interruption is not yet implemented. This endpoint is reserved for a future WebSocket-based transport upgrade that will support mid-session cancellation.")`.
- [x] Add a docstring comment on the endpoint noting: "This is the intended hook point for future WebSocket upgrade. When implemented, it should send an interrupt signal to the running claude_agent_sdk query coroutine identified by session_id."

---

## 7. Message Serialisation

- [x] Define a module-level `_sse_counter = 0` integer for SSE frame IDs (increment before each yield, not after).
- [x] Define a `serialize_message(msg: Any) -> tuple[str, str]` function that returns `(event_type, json_data_string)`:
  - `StreamEvent` → event type `"stream_event"`
  - `AssistantMessage` → event type `"assistant_message"`
  - `UserMessage` → event type `"user_message"`
  - `ResultMessage` → event type `"result_message"`
  - `SystemMessage` → event type `"system_message"`
  - Any other / unknown type → event type `"unknown"`, serialise with `str(msg)`
- [x] Define a `ProxyJsonEncoder(json.JSONEncoder)` subclass that handles:
  - `datetime` objects → `.isoformat()` string
  - `Path` objects → `str(obj)`
  - `bytes` objects → `base64.b64encode(obj).decode("ascii")`
  - `dataclasses.dataclass` instances → `dataclasses.asdict(obj)` (recurse through the encoder)
  - Fall back to `super().default(obj)` for anything else
- [x] Apply `ProxyJsonEncoder` in a helper `to_json(obj: Any) -> str` that calls `json.dumps(obj, cls=ProxyJsonEncoder)`.
- [x] Each SSE frame format (exactly, with CRLF or LF both acceptable per the SSE spec — use `\n`):
  ```
  id: {counter}\n
  event: {event_type}\n
  data: {json_string}\n
  \n
  ```
- [x] Include the `id:` line on every frame even though reconnection is not implemented server-side; it is good SSE hygiene and costs nothing.

---

## 8. Startup Banner

Print this banner **after** all checks have passed and the uvicorn server and tunnel (if any) are fully initialised. Use plain `print()` calls (not `logging`) so the banner always appears regardless of log level.

- [x] Banner must include:
  - A header line: `Claude Code Proxy Server is running`
  - Local server URL: `http://{host}:{port}`
  - Tunnel URL (if configured): the value of `TUNNEL_URL`; omit or print `"N/A"` if no tunnel
  - Bearer token (masked): show first 8 characters followed by `...` (e.g. `abcd1234...`); never print the full token in the banner after the one-time generation notice in section 3.5
  - Configured CWD: the value of `--cwd` or `"unrestricted"` if not set
  - Allowed CWD paths: the value of `--allowed-cwd-paths` or `"any"`
  - Active tunnel type: `ngrok | cloudflare | ssh | none`
  - Example curl command for a health check:
    ```
    curl http://127.0.0.1:{port}/health
    ```
  - Example curl command for a query (using the masked token — instruct the user to replace with their actual token):
    ```
    curl -N -H "Authorization: Bearer <your_token>" \
         -H "Content-Type: application/json" \
         -d '{"prompt": "Hello"}' \
         http://127.0.0.1:{port}/query
    ```
  - AiCore client config YAML snippet showing exactly what to paste into their `config.yml`:
    ```yaml
    llm:
      provider: remote_claude_code
      base_url: http://127.0.0.1:{port}   # or the tunnel URL
      api_key: <your_token>
      model: claude-opus-4-5
    ```

---

## 9. Logging

- [x] Call `logging.basicConfig(level=args.log_level, format="%(asctime)s | %(levelname)s | %(message)s")` at the very start of `main()`, before any startup checks run.
- [x] Use `logger = logging.getLogger(__name__)` at module level (do not use `print()` for internal log messages after startup banners and user-facing print statements are done).
- [x] Log level `DEBUG`: full serialised SSE frame content (helpful for development/debugging of the client).
- [x] Log level `INFO`: request start/completion events, server start/stop, tunnel URL.
- [x] Log level `WARNING`: soft failures (auth warning from CLI check, missing optional packages).
- [x] Log level `ERROR`: hard failures before `sys.exit(1)` calls (so the reason appears in redirected logs).
- [x] Each `/query` request start log entry must include: client IP, model, prompt character count, effective options summary (omit prompt content).
- [x] Each `/query` completion log entry must include: `session_id`, `total_cost_usd`, `num_turns`, `duration_ms` formatted to two decimal places.
- [x] Do **not** log the prompt content at `INFO` level — only at `DEBUG` level, to avoid sensitive data appearing in default logs.

---

## 10. Module Entry Point

- [x] Implement a `main()` function that orchestrates: argument parsing → startup checks → tunnel setup → FastAPI app wiring → banner printing → `uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())`.
- [x] Wrap the `uvicorn.run()` call in a `try/except KeyboardInterrupt` block and print `"\nProxy server stopped by user (Ctrl+C)."` on interrupt.
- [x] End the file with:
  ```python
  if __name__ == "__main__":
      main()
  ```

---

## 11. Future Work / Known Limitations (document these as comments in the code)

- [x] Session interruption (DELETE /query/{session_id}) requires a WebSocket transport and a way to hold a reference to a running async generator by session ID.
- [x] The server is single-process; horizontal scaling is out of scope.
- [x] No persistent session state — each POST /query creates a fresh `claude_agent_sdk.query()` call.
- [x] The ngrok free tier imposes connection limits and session time limits; a paid plan or alternative tunnel is recommended for sustained use.
- [x] Rate limiting and per-client quotas are not implemented; consider adding a middleware layer if exposing this server beyond a trusted LAN.
