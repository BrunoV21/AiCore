CC_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"

CC_DEFAULT_QUERY = {
    "beta": "true"
}

CC_DEFAULT_HEADERS = {
    "anthropic-beta": "claude-code-20250219,oauth-2025-04-20,interleaved-thinking-2025-05-14,fine-grained-tool-streaming-2025-05-14",
    "anthropic-dangerous-direct-browser-access": "true",
    "user-agent": "claude-cli/1.0.84 (external, cli)",
    "x-app": "cli"
}

CC_SYSTEM_PROMPT = "You are Claude Code, Anthropic's official CLI for Claude."

BETA_1M_CONTEXT_HEADERS = {
    "anthropic-beta": "context-1m-2025-08-07"
}