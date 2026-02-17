"""
aicore.scripts.claude_code_proxy_server
=========================================
Claude Code Proxy Server — FastAPI SSE service for remote Claude Code access.

Wraps ``claude-agent-sdk``'s ``query()`` function as a FastAPI SSE endpoint
protected by Bearer token authentication.  Run this on any machine that has
the Claude Code CLI installed and authenticated; then point
``RemoteClaudeCodeLlm`` at it from any other machine.

Entry points
------------
::

    # Recommended — registered by setup.py console_scripts
    aicore-proxy-server [OPTIONS]

    # Alternative — Python module invocation
    python -m aicore.scripts.claude_code_proxy_server [OPTIONS]

Installation
------------
Install the server-side extras (FastAPI, uvicorn, python-dotenv)::

    pip install core-for-ai[claude-server]

Also required on the server machine::

    npm install -g @anthropic-ai/claude-code   # Claude Code CLI
    claude login                                # one-time authentication
    pip install claude-agent-sdk               # Python SDK

Optional::

    pip install pyngrok    # only needed for --tunnel ngrok

CLI options
-----------
--host HOST
    Bind address (default: ``127.0.0.1``).  Use ``0.0.0.0`` for LAN access.
--port PORT
    TCP port (default: ``8080``).
--token TOKEN
    Bearer token for client authentication.  Also readable from the
    ``CLAUDE_PROXY_TOKEN`` environment variable.  Auto-generated (and printed)
    if omitted.
--tunnel {none,ngrok,cloudflare,ssh}
    Tunnel method.  Omit to be prompted interactively at startup.
    ``ngrok`` stores the auth token in the OS credential store on first run.
--tunnel-port PORT
    Remote port for SSH tunnels (defaults to ``--port``).
--cwd PATH
    Force a working directory for all Claude sessions on this server.
--allowed-cwd-paths PATH [PATH ...]
    Whitelist of ``cwd`` values that clients may request.
--log-level {DEBUG,INFO,WARNING,ERROR}
    Logging verbosity (default: ``INFO``).
--cors-origins ORIGIN [ORIGIN ...]
    Allowed CORS origins (default: ``*``).

Tunnel modes
------------
none
    No tunnel — server only reachable on the local network.
ngrok
    Public HTTPS tunnel via pyngrok.  On first run the user is prompted for
    their ngrok auth token, which is then stored in the OS credential store
    (Windows Credential Manager / macOS Keychain / Linux Secret Service) and
    loaded automatically on subsequent runs.
cloudflare
    Public HTTPS tunnel via the ``cloudflared`` binary (must be on PATH).
ssh
    Prints the ``ssh -R`` command to set up a reverse tunnel to your own VPS.
    No extra software needed; requires a VPS with ``GatewayPorts yes`` in
    ``/etc/ssh/sshd_config``.

API endpoints
-------------
GET  /health
    Returns server status, uptime, Claude CLI version, and active stream count.
    No authentication required.

GET  /capabilities
    Returns supported options and server-enforced defaults.
    Requires Bearer token.

POST /query
    Accepts ``{"prompt": "...", "options": {...}, "system_prompt": "..."}``
    and streams the ``claude-agent-sdk`` response as SSE frames.
    Requires Bearer token.

    SSE event types: ``stream_event``, ``assistant_message``, ``user_message``,
    ``result_message``, ``system_message``, ``error``.

DELETE /query/{session_id}
    Reserved for future WebSocket-based mid-session cancellation.
    Currently returns HTTP 501.

Token persistence
-----------------
The Bearer token is resolved in this order:

1. ``--token`` CLI argument
2. ``CLAUDE_PROXY_TOKEN`` environment variable (or ``.env`` file if
   ``python-dotenv`` is installed)
3. Auto-generated ``secrets.token_urlsafe(32)`` — printed at startup

To reuse the same token across restarts add it to a ``.env`` file::

    echo 'CLAUDE_PROXY_TOKEN=your_token' >> .env

Quick-start example
-------------------
Server (machine with Claude Code CLI)::

    pip install core-for-ai[claude-server]
    aicore-proxy-server --port 8080 --tunnel none

Client (any machine)::

    # config.yml
    llm:
      provider: "remote_claude_code"
      model: "claude-sonnet-4-5-20250929"
      base_url: "http://server-ip:8080"
      api_key: "token-printed-at-startup"

Known limitations
-----------------
- Session interruption (``DELETE /query/{session_id}``) is not yet implemented;
  it requires a WebSocket transport to hold a cancellable reference to the
  running async generator.
- Single-process only; horizontal scaling is out of scope.
- No persistent session state — each ``POST /query`` creates a fresh
  ``claude-agent-sdk`` session.
- Rate limiting and per-client quotas are not implemented.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import dataclasses
import hmac
import importlib.metadata
import json
import logging
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional import: python-dotenv
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False
    logging.warning(
        "python-dotenv is not installed. .env files will not be loaded automatically.\n"
        "Install it with: pip install python-dotenv"
    )

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state (populated during startup)
# ---------------------------------------------------------------------------
PROXY_TOKEN: str = ""
TUNNEL_URL: Optional[str] = None
SERVER_START_TIME: float = 0.0
CLAUDE_CLI_VERSION: str = "unknown"
_active_streams: int = 0
_active_streams_lock = threading.Lock()
_sse_counter: int = 0
_tunnel_process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
_server_version = "1.0.0"

# ---------------------------------------------------------------------------
# Context manager: unset env vars (mirrors claude_code/local.py)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _unset_env(*keys: str):
    """Temporarily remove environment variables for the duration of the block."""
    saved = {k: os.environ.pop(k) for k in keys if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


# ===========================================================================
# JSON encoder
# ===========================================================================
class ProxyJsonEncoder(json.JSONEncoder):
    """Extended JSON encoder that handles extra Python types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("ascii")
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return super().default(obj)


def to_json(obj: Any) -> str:
    return json.dumps(obj, cls=ProxyJsonEncoder)


# ===========================================================================
# Message serialisation
# ===========================================================================
def _block_to_dict(block: Any) -> dict:
    """Convert a content block dataclass to a dict, injecting a 'type' discriminator.

    The SDK block dataclasses (TextBlock, ToolUseBlock, ToolResultBlock,
    ThinkingBlock) have NO 'type' field of their own.  Without an explicit
    discriminator the remote deserialiser cannot reconstruct the correct class.
    """
    try:
        from claude_agent_sdk.types import TextBlock, ToolUseBlock, ToolResultBlock  # type: ignore
        try:
            from claude_agent_sdk.types import ThinkingBlock  # type: ignore
        except ImportError:
            ThinkingBlock = None

        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        if isinstance(block, ToolUseBlock):
            return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
        if isinstance(block, ToolResultBlock):
            return {"type": "tool_result", "tool_use_id": block.tool_use_id,
                    "content": block.content, "is_error": block.is_error}
        if ThinkingBlock is not None and isinstance(block, ThinkingBlock):
            return {"type": "thinking", "thinking": block.thinking,
                    "signature": getattr(block, "signature", "")}
    except Exception:
        pass
    # Fallback: use dataclasses.asdict (type field will be absent but at least the data is there)
    if dataclasses.is_dataclass(block) and not isinstance(block, type):
        return dataclasses.asdict(block)
    return {"type": "unknown", "raw": str(block)}


def serialize_message(msg: Any) -> tuple[str, str]:
    """Return (event_type, json_data_string) for an SDK message."""
    try:
        from claude_agent_sdk import AssistantMessage, UserMessage, ResultMessage  # type: ignore
        from claude_agent_sdk.types import StreamEvent  # type: ignore
    except ImportError:
        return "unknown", to_json({"raw": str(msg)})

    # Attempt to also import SystemMessage (may not exist in all SDK versions)
    try:
        from claude_agent_sdk import SystemMessage  # type: ignore
        _system_msg_type = SystemMessage
    except ImportError:
        _system_msg_type = None

    if isinstance(msg, StreamEvent):
        event_type = "stream_event"
    elif isinstance(msg, AssistantMessage):
        event_type = "assistant_message"
    elif isinstance(msg, UserMessage):
        event_type = "user_message"
    elif isinstance(msg, ResultMessage):
        event_type = "result_message"
    elif _system_msg_type is not None and isinstance(msg, _system_msg_type):
        event_type = "system_message"
    else:
        event_type = "unknown"
        return event_type, to_json({"raw": str(msg)})

    # For messages that carry content block lists, inject type discriminators so
    # the remote deserialiser can reconstruct the correct block class.
    if isinstance(msg, (AssistantMessage, UserMessage)):
        raw_content = msg.content
        if isinstance(raw_content, list):
            serialized_content = [_block_to_dict(b) for b in raw_content]
        else:
            serialized_content = raw_content  # str passthrough for UserMessage

        # Build the rest of the message dict via dataclasses.asdict (excludes content)
        if dataclasses.is_dataclass(msg) and not isinstance(msg, type):
            data = dataclasses.asdict(msg)
        else:
            data = getattr(msg, "__dict__", {})
        data["content"] = serialized_content
        return event_type, to_json(data)

    if dataclasses.is_dataclass(msg) and not isinstance(msg, type):
        data = dataclasses.asdict(msg)
    else:
        try:
            data = msg.__dict__
        except AttributeError:
            data = {"raw": str(msg)}

    return event_type, to_json(data)


def _make_sse_frame(event_type: str, json_data: str) -> str:
    global _sse_counter
    _sse_counter += 1
    frame = f"id: {_sse_counter}\nevent: {event_type}\ndata: {json_data}\n\n"
    logger.debug("SSE frame: %s", frame)
    return frame


# ===========================================================================
# CLI argument parsing
# ===========================================================================
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aicore-proxy-server",
        description="Claude Code Proxy Server — serves claude_agent_sdk.query() over SSE/HTTP.",
    )
    parser.add_argument("--port", type=int, default=8080, help="TCP port (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--token", type=str, default=None, help="Override proxy token (also settable via CLAUDE_PROXY_TOKEN)")
    parser.add_argument(
        "--tunnel",
        type=str,
        choices=["ngrok", "cloudflare", "ssh", "none"],
        default=None,  # None means "ask interactively at startup"
        help="Tunnel method. If omitted, you will be prompted interactively.",
    )
    parser.add_argument("--cwd", type=str, default=None, help="Working directory for Claude Code CLI")
    parser.add_argument(
        "--allowed-cwd-paths",
        nargs="*",
        default=[],
        help="Whitelist of allowed cwd roots for client requests",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--cors-origins",
        nargs="*",
        default=["*"],
        help="CORS allowed origins (default: *)",
    )
    parser.add_argument(
        "--tunnel-port",
        type=int,
        default=None,
        help="Remote port for SSH tunnels (defaults to --port)",
    )
    return parser.parse_args(argv)


# ===========================================================================
# Startup checks
# ===========================================================================
def check_python_version() -> None:
    print("[1/5] Checking Python version...")
    if sys.version_info < (3, 11):
        print(
            f"ERROR: Python 3.11+ is required. You are running Python {sys.version}. Please upgrade."
        )
        sys.exit(1)
    print(f"  [OK] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")


def check_sdk() -> None:
    print("[2/5] Checking claude-agent-sdk...")
    try:
        import claude_agent_sdk  # type: ignore  # noqa: F401
        print("  [OK] claude-agent-sdk is installed")
    except ImportError:
        print(
            "ERROR: claude-agent-sdk is not installed.\n"
            "Install it with: pip install claude-agent-sdk\n"
            "Docs: https://platform.claude.com/docs/en/agent-sdk/python"
        )
        sys.exit(1)


def check_claude_cli() -> None:
    print("[3/5] Checking Claude CLI on PATH...")
    if shutil.which("claude") is None:
        print(
            "ERROR: The 'claude' CLI is not on your PATH.\n"
            "Install it with: npm install -g @anthropic-ai/claude-code\n"
            "Docs: https://docs.anthropic.com/en/docs/claude-code/getting-started"
        )
        sys.exit(1)
    print("  [OK] 'claude' CLI found at: " + shutil.which("claude"))  # type: ignore[arg-type]


def check_claude_auth() -> None:
    global CLAUDE_CLI_VERSION
    print("[4/5] Checking Claude CLI authentication...")
    try:
        # On Windows, .CMD/.BAT files require shell=True to be invoked correctly.
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=(sys.platform == "win32"),
        )
        CLAUDE_CLI_VERSION = (result.stdout or "").strip() or "unknown"
        combined = (result.stdout + result.stderr).lower()
        auth_keywords = ("not logged in", "auth", "login", "token")
        if result.returncode != 0 or any(kw in combined for kw in auth_keywords):
            print(
                "  WARNING: Claude CLI may not be authenticated. Run 'claude login' and then retry.\n"
                "  If you are already authenticated, this warning can be ignored."
            )
        else:
            print(f"  [OK] Claude CLI version: {CLAUDE_CLI_VERSION}")
    except Exception as exc:
        print(f"  WARNING: Could not run 'claude --version': {exc}")


def setup_proxy_token(args: argparse.Namespace) -> None:
    global PROXY_TOKEN
    print("[5/5] Setting up proxy token...")

    if _HAS_DOTENV:
        _load_dotenv()

    if args.token:
        PROXY_TOKEN = args.token
        print("  [OK] Proxy token loaded (set via CLI arg)")
    elif "CLAUDE_PROXY_TOKEN" in os.environ:
        PROXY_TOKEN = os.environ["CLAUDE_PROXY_TOKEN"]
        print("  [OK] Proxy token loaded (set via CLAUDE_PROXY_TOKEN env var)")
    else:
        PROXY_TOKEN = secrets.token_urlsafe(32)
        print(
            "============================================================\n"
            "GENERATED PROXY TOKEN (ephemeral — not saved automatically)\n"
            f"Token: {PROXY_TOKEN}\n"
            "\n"
            "To persist this token across restarts, add it to your .env file:\n"
            f"  echo 'CLAUDE_PROXY_TOKEN={PROXY_TOKEN}' >> .env\n"
            "Or pass it at startup:\n"
            f"  aicore-proxy-server --token {PROXY_TOKEN}\n"
            "============================================================"
        )


def print_config_summary(args: argparse.Namespace) -> None:
    cwd_display = args.cwd if args.cwd else "unrestricted"
    allowed_display = str(args.allowed_cwd_paths) if args.allowed_cwd_paths else "any"
    tunnel_display = args.tunnel if args.tunnel is not None else "(will prompt)"
    print(
        "\n"
        "┌─ Configuration ──────────────────────────────────┐\n"
        f"│ Port           : {args.port:<32}│\n"
        f"│ Host           : {args.host:<32}│\n"
        f"│ CWD            : {cwd_display:<32}│\n"
        f"│ Allowed CWDs   : {allowed_display:<32}│\n"
        f"│ Tunnel         : {tunnel_display:<32}│\n"
        f"│ Log level      : {args.log_level:<32}│\n"
        f"│ Claude version : {CLAUDE_CLI_VERSION:<32}│\n"
        "└───────────────────────────────────────────────────┘"
    )


# ===========================================================================
# Interactive tunnel selection
# ===========================================================================
_TUNNEL_CHOICES = {
    "1": "none",
    "2": "ngrok",
    "3": "cloudflare",
    "4": "ssh",
}

def prompt_tunnel_choice() -> str:
    """Interactively ask the user which tunnel method to use.

    Returns one of: 'none', 'ngrok', 'cloudflare', 'ssh'.
    Falls back to 'none' on EOF (non-interactive / piped input).
    """
    print(
        "\nHow should the proxy server be exposed?\n"
        "\n"
        "  [1] none        — local network only (default)\n"
        "  [2] ngrok       — public HTTPS tunnel via ngrok (requires pyngrok)\n"
        "  [3] cloudflare  — public HTTPS tunnel via cloudflared binary\n"
        "  [4] ssh         — print SSH reverse-tunnel command for your own VPS\n"
    )
    while True:
        try:
            raw = input("Select tunnel [1-4, default=1]: ").strip()
        except EOFError:
            # Non-interactive environment (e.g. piped input) — default to none
            print("  (non-interactive mode detected, defaulting to 'none')")
            return "none"

        if raw == "" or raw == "1":
            return "none"
        if raw in _TUNNEL_CHOICES:
            return _TUNNEL_CHOICES[raw]
        # Also accept typing the name directly
        if raw in ("none", "ngrok", "cloudflare", "ssh"):
            return raw
        print(f"  Invalid choice '{raw}'. Please enter a number 1-4 or the name.")


# ===========================================================================
# Credential store helpers (ngrok auth token persistence)
# ===========================================================================
_CRED_SERVICE = "aicore-proxy-server"
_CRED_USERNAME = "ngrok_auth_token"


def _store_ngrok_token(token: str) -> None:
    """Persist the ngrok auth token in the OS credential store.

    Tries keyring first and verifies the write by reading back immediately.
    Falls through to the native platform store if keyring is unavailable or
    the round-trip verification fails.
    """
    # --- primary: keyring — only trust it if readback confirms the write ---
    try:
        import keyring  # type: ignore
        keyring.set_password(_CRED_SERVICE, _CRED_USERNAME, token)
        readback = keyring.get_password(_CRED_SERVICE, _CRED_USERNAME)
        if readback == token:
            print(
                "  [OK] ngrok auth token saved to the OS credential store via keyring.\n"
                "  It will be retrieved automatically on the next run."
            )
            return
        # Readback mismatch — keyring silently used a no-op backend
        print("  WARNING: keyring did not persist the token (no usable backend). Trying native store...")
    except ImportError:
        pass
    except Exception as exc:
        print(f"  WARNING: keyring store failed ({exc}). Trying native store...")

    # --- native platform fallback ---
    if sys.platform == "win32":
        _store_ngrok_token_windows(token)
    elif sys.platform == "darwin":
        _store_ngrok_token_macos(token)
    else:
        _store_ngrok_token_linux(token)


def _retrieve_ngrok_token() -> Optional[str]:
    """Retrieve the ngrok auth token from the OS credential store.

    Tries keyring first; if it returns nothing, falls through to the native
    platform store so a token saved by a previous fallback is still found.
    """
    # --- primary: keyring ---
    try:
        import keyring  # type: ignore
        val = keyring.get_password(_CRED_SERVICE, _CRED_USERNAME)
        if val:
            return val
        # val is None — keyring found nothing; try native in case the token
        # was stored by the native path in a previous run
    except ImportError:
        pass
    except Exception as exc:
        print(f"  WARNING: keyring retrieve failed ({exc}). Trying native store...")

    # --- native platform fallback ---
    if sys.platform == "win32":
        return _retrieve_ngrok_token_windows()
    elif sys.platform == "darwin":
        return _retrieve_ngrok_token_macos()
    else:
        return _retrieve_ngrok_token_linux()


# --- Windows: PowerShell PasswordVault ---

def _store_ngrok_token_windows(token: str) -> None:
    # Inject service/username/token via environment variables to avoid any
    # quoting or injection issues with special characters in the token value.
    script = (
        '$vault = New-Object Windows.Security.Credentials.PasswordVault;'
        '$cred  = New-Object Windows.Security.Credentials.PasswordCredential('
        '  $env:_CC_SVC, $env:_CC_USR, $env:_CC_TOK);'
        '$vault.Add($cred)'
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    env = {**os.environ, "_CC_SVC": _CRED_SERVICE, "_CC_USR": _CRED_USERNAME, "_CC_TOK": token}
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True, text=True, env=env,
        )
        if result.returncode == 0:
            print(
                "  [OK] ngrok auth token saved to Windows Credential Manager (PasswordVault).\n"
                "  It will be retrieved automatically on the next run."
            )
        else:
            print(f"  WARNING: PasswordVault store failed: {result.stderr.strip()}")
    except Exception as exc:
        print(f"  WARNING: Could not store token in Windows Credential Manager: {exc}")


def _retrieve_ngrok_token_windows() -> Optional[str]:
    # Service and username are injected via environment variables.
    # -EncodedCommand ensures the exit code inside try/catch propagates correctly.
    script = (
        '$vault = New-Object Windows.Security.Credentials.PasswordVault;'
        'try {'
        '  $c = $vault.Retrieve($env:_CC_SVC, $env:_CC_USR);'
        '  $c.RetrievePassword();'
        '  Write-Output $c.Password;'
        '  exit 0'
        '} catch {'
        '  exit 1'
        '}'
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    env = {**os.environ, "_CC_SVC": _CRED_SERVICE, "_CC_USR": _CRED_USERNAME}
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True, text=True, env=env,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        logger.debug("PasswordVault retrieve exited %d: %s", result.returncode, result.stderr.strip())
    except Exception as exc:
        logger.debug("PasswordVault retrieve failed: %s", exc)
    return None


# --- macOS: Keychain via security CLI ---

def _store_ngrok_token_macos(token: str) -> None:
    try:
        result = subprocess.run(
            [
                "security", "add-generic-password",
                "-U",                    # update if already exists
                "-s", _CRED_SERVICE,
                "-a", _CRED_USERNAME,
                "-w", token,
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(
                "  [OK] ngrok auth token saved to macOS Keychain.\n"
                "  It will be retrieved automatically on the next run."
            )
        else:
            print(f"  WARNING: Keychain store failed: {result.stderr.strip()}")
    except Exception as exc:
        print(f"  WARNING: Could not store token in macOS Keychain: {exc}")


def _retrieve_ngrok_token_macos() -> Optional[str]:
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", _CRED_SERVICE,
                "-a", _CRED_USERNAME,
                "-w",                    # print password only
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception as exc:
        logger.debug("Keychain retrieve failed: %s", exc)
    return None


# --- Linux: libsecret via secret-tool ---

def _store_ngrok_token_linux(token: str) -> None:
    if not shutil.which("secret-tool"):
        print(
            "  WARNING: 'secret-tool' not found. Install libsecret-tools to persist the token:\n"
            "    sudo apt install libsecret-tools   # Debian/Ubuntu\n"
            "    sudo dnf install libsecret          # Fedora\n"
            "  Token will only be available for this session."
        )
        return
    try:
        proc = subprocess.Popen(
            [
                "secret-tool", "store",
                "--label", "AiCore ngrok auth token",
                "service", _CRED_SERVICE,
                "username", _CRED_USERNAME,
            ],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        _, stderr = proc.communicate(input=token)
        if proc.returncode == 0:
            print(
                "  [OK] ngrok auth token saved to the Linux Secret Service (GNOME Keyring / KWallet).\n"
                "  It will be retrieved automatically on the next run."
            )
        else:
            print(f"  WARNING: secret-tool store failed: {stderr.strip()}")
    except Exception as exc:
        print(f"  WARNING: Could not store token via secret-tool: {exc}")


def _retrieve_ngrok_token_linux() -> Optional[str]:
    if not shutil.which("secret-tool"):
        return None
    try:
        result = subprocess.run(
            [
                "secret-tool", "lookup",
                "service", _CRED_SERVICE,
                "username", _CRED_USERNAME,
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception as exc:
        logger.debug("secret-tool lookup failed: %s", exc)
    return None


# ===========================================================================
# Tunnel setup
# ===========================================================================
def setup_tunnel_ngrok(port: int) -> None:
    global TUNNEL_URL
    try:
        import pyngrok.ngrok as ngrok  # type: ignore
    except ImportError:
        print(
            "ERROR: pyngrok is required for ngrok tunnels.\n"
            "Install it with: pip install pyngrok"
        )
        sys.exit(1)

    # Resolution order: env var → credential store → interactive prompt
    ngrok_token = os.environ.get("NGROK_AUTH_TOKEN")

    if not ngrok_token:
        print("  Checking OS credential store for ngrok auth token...")
        ngrok_token = _retrieve_ngrok_token()
        if ngrok_token:
            print("  [OK] ngrok auth token loaded from the OS credential store.")

    if not ngrok_token:
        print(
            "\n  No ngrok auth token found.\n"
            "  To use ngrok you need a free account and an auth token:\n"
            "    1. Sign up or log in at https://dashboard.ngrok.com\n"
            "    2. Go to https://dashboard.ngrok.com/get-started/your-authtoken\n"
            "    3. Copy your token and paste it below.\n"
            "  (Leave blank to abort and fall back to no tunnel.)\n"
        )
        try:
            entered = input("  Enter your ngrok auth token: ").strip()
        except EOFError:
            entered = ""

        if not entered:
            print("  No token provided — aborting ngrok setup. Falling back to no tunnel.")
            setup_tunnel_none(port)
            return

        ngrok_token = entered
        print("  Saving token to the OS credential store...")
        _store_ngrok_token(ngrok_token)

    ngrok.set_auth_token(ngrok_token)
    tunnel = ngrok.connect(port, proto="http")
    TUNNEL_URL = tunnel.public_url
    print(f"  [OK] ngrok tunnel active: {TUNNEL_URL}")
    print("  NOTE: Free ngrok URLs are ephemeral and change on every restart.")


def setup_tunnel_cloudflare(port: int) -> None:
    global TUNNEL_URL, _tunnel_process
    if not shutil.which("cloudflared"):
        print(
            "ERROR: 'cloudflared' binary not found on PATH.\n"
            "Download it from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
        )
        sys.exit(1)

    print("  Starting Cloudflare quick tunnel...")
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stderr=subprocess.PIPE,
        text=True,
    )
    _tunnel_process = proc

    url_pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    assert proc.stderr is not None
    for line in proc.stderr:
        match = url_pattern.search(line)
        if match:
            TUNNEL_URL = match.group(0)
            break

    if TUNNEL_URL:
        print(f"  [OK] Cloudflare tunnel active: {TUNNEL_URL}")
    else:
        print("  WARNING: Could not extract Cloudflare tunnel URL from cloudflared output.")

    print(
        "  NOTE: Quick tunnels are ephemeral. For a stable URL, use a named tunnel\n"
        "  (requires a Cloudflare account): https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/"
    )


def setup_tunnel_ssh(port: int, tunnel_port: int) -> None:
    global TUNNEL_URL
    print(
        "\nRun the following command on your local machine to expose the proxy server:\n"
        "\n"
        f"  ssh -R {tunnel_port}:localhost:{port} user@your-vps -N\n"
        "\n"
        "Replace 'user@your-vps' with your VPS credentials and remote_port with the desired remote port.\n"
        "Ensure 'GatewayPorts yes' is set in /etc/ssh/sshd_config on your VPS and that sshd was reloaded.\n"
        "\n"
        "The proxy server will then be reachable at:\n"
        f"  http://your-vps-ip:{tunnel_port}"
    )
    TUNNEL_URL = None


def setup_tunnel_none(port: int) -> None:
    try:
        addrs = {
            info[4][0]
            for info in socket.getaddrinfo(socket.gethostname(), None)
            if info[0] == socket.AF_INET
        }
    except Exception:
        try:
            addrs = {socket.gethostbyname(socket.gethostname())}
        except Exception:
            addrs = set()

    addrs.add("127.0.0.1")
    lan_lines = "\n".join(f"  http://{addr}:{port}" for addr in sorted(addrs))
    print(
        "  NOTE: Server is only accessible on the local network (no tunnel configured).\n"
        "  LAN addresses:\n" + lan_lines
    )


def setup_tunnel(args: argparse.Namespace) -> None:
    tunnel_port = args.tunnel_port if args.tunnel_port is not None else args.port
    if args.tunnel == "ngrok":
        setup_tunnel_ngrok(args.port)
    elif args.tunnel == "cloudflare":
        setup_tunnel_cloudflare(args.port)
    elif args.tunnel == "ssh":
        setup_tunnel_ssh(args.port, tunnel_port)
    else:
        setup_tunnel_none(args.port)


# ===========================================================================
# Pydantic models (module-level — required for Pydantic v2 / FastAPI 0.100+)
# ===========================================================================
try:
    from pydantic import BaseModel as _PydanticBaseModel

    class HealthResponse(_PydanticBaseModel):
        status: str
        server_version: str
        claude_cli_version: str
        uptime_seconds: float
        active_streams: int
        authenticated: bool

    class CapabilitiesResponse(_PydanticBaseModel):
        server_version: str
        sdk_version: str
        supported_options: List[str]
        server_enforced_defaults: Dict[str, Any]
        cwd_whitelist: List[str]

    class QueryRequest(_PydanticBaseModel):
        prompt: str
        system_prompt: Optional[str] = None
        options: Optional[Dict[str, Any]] = None

        def model_post_init(self, __context: Any) -> None:
            if self.options is None:
                self.options = {}

except ImportError:
    # pydantic not installed yet — will fail later when build_app() is called
    HealthResponse = None  # type: ignore[assignment,misc]
    CapabilitiesResponse = None  # type: ignore[assignment,misc]
    QueryRequest = None  # type: ignore[assignment,misc]


# ===========================================================================
# FastAPI application
# ===========================================================================
def build_app(args: argparse.Namespace):
    from fastapi import Depends, FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    # CORS is wide-open by default because this is a developer tool not intended
    # to be exposed publicly without a proper bearer token in place.
    app = FastAPI(title="Claude Code Proxy Server", version=_server_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=args.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    # ------------------------------------------------------------------
    # Request logging middleware
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "%s %s from %s → %s",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
            response.status_code,
        )
        return response

    # ------------------------------------------------------------------
    # Shutdown handler
    # ------------------------------------------------------------------
    @app.on_event("shutdown")
    async def on_shutdown():
        global _tunnel_process
        print("Claude Code Proxy Server shutting down. Goodbye.")
        if _tunnel_process is not None:
            try:
                _tunnel_process.terminate()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Bearer token auth dependency
    # ------------------------------------------------------------------
    _bearer_scheme = HTTPBearer(auto_error=True)

    async def verify_token(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    ):
        ok = hmac.compare_digest(credentials.credentials, PROXY_TOKEN)
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")

    # ------------------------------------------------------------------
    # GET /health — no auth
    # ------------------------------------------------------------------
    @app.get("/health", response_model=HealthResponse)
    async def health():
        with _active_streams_lock:
            current_streams = _active_streams
        return HealthResponse(
            status="ok",
            server_version=_server_version,
            claude_cli_version=CLAUDE_CLI_VERSION,
            uptime_seconds=time.time() - SERVER_START_TIME,
            active_streams=current_streams,
            authenticated=True,
        )

    # ------------------------------------------------------------------
    # GET /capabilities — auth required
    # ------------------------------------------------------------------
    @app.get("/capabilities", response_model=CapabilitiesResponse)
    async def capabilities(_=Depends(verify_token)):
        try:
            sdk_ver = importlib.metadata.version("claude-agent-sdk")
        except importlib.metadata.PackageNotFoundError:
            sdk_ver = "unknown"

        enforced: Dict[str, Any] = {"include_partial_messages": True}
        if args.cwd:
            enforced["cwd"] = args.cwd

        return CapabilitiesResponse(
            server_version=_server_version,
            sdk_version=sdk_ver,
            supported_options=["model", "permission_mode", "cwd", "max_turns", "allowed_tools", "system_prompt"],
            server_enforced_defaults=enforced,
            cwd_whitelist=args.allowed_cwd_paths or [],
        )

    # ------------------------------------------------------------------
    # POST /query — auth required, SSE streaming
    # ------------------------------------------------------------------
    @app.post("/query")
    async def query_endpoint(req: QueryRequest, _=Depends(verify_token)):
        from claude_agent_sdk import query as sdk_query, ClaudeAgentOptions  # type: ignore

        client_ip = "unknown"
        opts_dict: Dict[str, Any] = dict(req.options or {})

        # --- CWD whitelist enforcement ---
        if args.allowed_cwd_paths:
            requested_cwd = opts_dict.get("cwd")
            if requested_cwd is not None:
                resolved = Path(requested_cwd).resolve()
                allowed = [Path(p).resolve() for p in args.allowed_cwd_paths]
                if not any(
                    str(resolved).startswith(str(root)) for root in allowed
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Requested cwd '{requested_cwd}' is not within the allowed paths: {args.allowed_cwd_paths}",
                    )

        # --- Option merging (server startup > request > server defaults) ---
        # Start with request options, then force server defaults
        opts_dict["include_partial_messages"] = True  # always force
        if args.cwd:
            opts_dict["cwd"] = args.cwd  # server startup config wins

        # --- Build ClaudeAgentOptions ---
        try:
            options = ClaudeAgentOptions(**opts_dict)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid options: {exc}") from exc

        # Inject system_prompt if provided
        if req.system_prompt:
            options.system_prompt = req.system_prompt

        model_name = opts_dict.get("model", "default")
        logger.info(
            "Query start | client=%s model=%s prompt_chars=%d options=%s",
            client_ip,
            model_name,
            len(req.prompt),
            {k: v for k, v in opts_dict.items() if k not in ("system_prompt",)},
        )

        start_time = time.time()

        async def stream_generator() -> AsyncGenerator[str, None]:
            global _active_streams
            with _active_streams_lock:
                _active_streams += 1

            session_id: Optional[str] = None
            total_cost: Optional[float] = None
            num_turns = 0

            try:
                from claude_agent_sdk import AssistantMessage, ResultMessage  # type: ignore

                with _unset_env("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
                    async for msg in sdk_query(prompt=req.prompt, options=options):
                        if isinstance(msg, AssistantMessage):
                            num_turns += 1
                        elif isinstance(msg, ResultMessage):
                            session_id = getattr(msg, "session_id", None)
                            total_cost = getattr(msg, "total_cost_usd", None)

                        event_type, json_data = serialize_message(msg)
                        yield _make_sse_frame(event_type, json_data)

            except Exception as exc:
                err_payload = to_json({"message": str(exc), "exit_code": getattr(exc, "exit_code", None)})
                yield _make_sse_frame("error", err_payload)
            finally:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "Query done  | session_id=%s cost_usd=%s turns=%d duration_ms=%.2f",
                    session_id or "n/a",
                    f"{total_cost:.6f}" if total_cost is not None else "n/a",
                    num_turns,
                    duration_ms,
                )
                with _active_streams_lock:
                    _active_streams -= 1

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # DELETE /query/{session_id} — stub, returns 501
    # This is the intended hook point for future WebSocket upgrade.
    # When implemented, it should send an interrupt signal to the running
    # claude_agent_sdk query coroutine identified by session_id.
    # ------------------------------------------------------------------
    @app.delete("/query/{session_id}")
    async def cancel_query(session_id: str, _=Depends(verify_token)):
        raise HTTPException(
            status_code=501,
            detail=(
                "Stream interruption is not yet implemented. This endpoint is reserved for a "
                "future WebSocket-based transport upgrade that will support mid-session cancellation."
            ),
        )

    return app


# ===========================================================================
# Startup banner
# ===========================================================================
def print_banner(args: argparse.Namespace) -> None:
    masked_token = PROXY_TOKEN#PROXY_TOKEN[:8] + "..." if len(PROXY_TOKEN) >= 8 else PROXY_TOKEN
    local_url = f"http://{args.host}:{args.port}"
    tunnel_display = TUNNEL_URL if TUNNEL_URL else "N/A"
    cwd_display = args.cwd if args.cwd else "unrestricted"
    allowed_display = str(args.allowed_cwd_paths) if args.allowed_cwd_paths else "any"

    print(
        "\n"
        "╔══════════════════════════════════════════════════════════╗\n"
        "║          Claude Code Proxy Server is running             ║\n"
        "╚══════════════════════════════════════════════════════════╝\n"
        f"\n  Local server URL : {local_url}"
        f"\n  Tunnel URL       : {tunnel_display}"
        f"\n  Bearer token     : {masked_token}   (replace with actual token in requests)"
        f"\n  CWD              : {cwd_display}"
        f"\n  Allowed CWD paths: {allowed_display}"
        f"\n  Tunnel type      : {args.tunnel}"
        "\n"
        "\n  ── Health check ─────────────────────────────────────────"
        f"\n  curl {local_url}/health"
        "\n"
        "\n  ── Example query ────────────────────────────────────────"
        f"\n  curl -N -H \"Authorization: Bearer <your_token>\" \\"
        f"\n       -H \"Content-Type: application/json\" \\"
        f"\n       -d '{{\"prompt\": \"Hello\"}}' \\"
        f"\n       {local_url}/query"
        "\n"
        "\n  ── AiCore config.yml snippet ────────────────────────────"
        "\n  llm:"
        "\n    provider: remote_claude_code"
        f"\n    base_url: {local_url}   # or the tunnel URL"
        "\n    api_key: <your_token>"
        "\n    model: claude-opus-4-5"
        "\n"
        "────────────────────────────────────────────────────────────\n"
    )


# ===========================================================================
# Main entry point
# ===========================================================================
def main(argv: Optional[List[str]] = None) -> None:
    global SERVER_START_TIME

    # On Windows, stdout/stderr may default to cp1252 which cannot encode box-drawing
    # characters used in the startup banners. Force UTF-8 with a safe fallback.
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args(argv)

    # Logging must be configured before any startup checks emit log records
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("\n=== Claude Code Proxy Server — startup checks ===\n")

    check_python_version()
    check_sdk()
    check_claude_cli()
    check_claude_auth()
    setup_proxy_token(args)
    print_config_summary(args)

    print("\n=== Tunnel setup ===\n")
    # Resolve tunnel choice: use CLI arg if supplied, otherwise ask interactively
    if args.tunnel is None:
        args.tunnel = prompt_tunnel_choice()
        print(f"  Tunnel selected: {args.tunnel}")
    else:
        print(f"  Tunnel pre-selected via --tunnel: {args.tunnel}")
    setup_tunnel(args)

    print("\n=== Building FastAPI application ===\n")
    app = build_app(args)

    print_banner(args)

    SERVER_START_TIME = time.time()

    try:
        import uvicorn  # type: ignore
    except ImportError:
        print(
            "ERROR: uvicorn is not installed.\n"
            "Install it with: pip install uvicorn[standard]"
        )
        sys.exit(1)

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())
    except KeyboardInterrupt:
        print("\nProxy server stopped by user (Ctrl+C).")


if __name__ == "__main__":
    main()
