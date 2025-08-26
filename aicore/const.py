import os
import json
from pathlib import Path

METADATA_JSON = Path(os.path.abspath(os.path.dirname(__file__))) / "models_metadata.json"

DEFAULT_CONFIG_PATH = os.getenv("CONFIG_PATH") or "./config/config.yml"

DEFAULT_MCP_JSON_PATH = os.getenv("MCP_JSON_PATH") or "./config/mcp_config.json"

DEFAULT_LOGS_DIR = os.getenv("LOGS_PATH") or "logs"

CUSTOM_MODELS = [
    # "gemini-2.0-flash-exp",
    # "gemini-2.0-flash-thinking-exp-01-21",
    # "gemini-2.5-pro-exp-03-25",
    # "gemini-2.5-pro-preview-03-25"
]

OPENAI_RESPONSE_ONLY_MODELS = [
    "o3-pro"
]

OPENAI_RESPONSE_API_MODELS = [
    "o1",
    "o3-mini", "o3", "o3-pro",
    "o4-mini",
    "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5-chat-latest"
]

try:
    custom_models = json.loads(os.getenv("CUSTOM_MODELS", "[]"))
    CUSTOM_MODELS.extend(custom_models)
except json.JSONDecodeError:
    print("\033[93m[WARNING] Passed CUSTOM_MODELS env var could not be parsed into JSON\033[0m")

SUPPORTED_REASONER_PROVIDERS = ["groq", "openrouter", "nvidia"]

SUPPORTED_REASONER_MODELS = [
    "deepseek-r1-distill-llama-70b", 
    "deepseek-ai/deepseek-r1",
    "deepseek/deepseek-r1:free"
]

GROQ_OPEN_AI_OSS_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

REASONING_START_TOKEN = "<think>"

REASONING_STOP_TOKEN = "</think>"

TOOL_CALL_START_TOKEN = "<tool>"

TOOL_CALL_END_TOKEN = "</tool>"

STREAM_START_TOKEN = "<start>"

STREAM_END_TOKEN = "</end>"

SPECIAL_TOKENS = [
    REASONING_START_TOKEN,
    REASONING_STOP_TOKEN,
    TOOL_CALL_START_TOKEN,
    TOOL_CALL_END_TOKEN,
    STREAM_START_TOKEN,
    STREAM_END_TOKEN
]

DEFAULT_ENCODING = "utf8"

# Tenacity constants
DEFAULT_MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "0")) or 5
DEFAULT_WAIT_MIN = int(os.getenv("WAIT_MIN", "0")) or 1
DEFAULT_WAIT_MAX = int(os.getenv("WAIT_MAX", "0")) or 60
DEFAULT_WAIT_EXP_MULTIPLIER = int(os.getenv("WAIT_EXP_MULTIPLIER", "0")) or 1

DEFAULT_TIMEOUT = int(os.getenv("AICORE_TIMEOUT", 20*60))

# Observability constants
DEFAULT_OBSERVABILITY_DIR = os.getenv("OBSERVABILITY_DIR") or "observability_data"
DEFAULT_OBSERVABILITY_FILE = os.getenv("OBSERVABILITY_FILE") or "llm_operations.json"