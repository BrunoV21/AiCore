import os
import json

DEFAULT_CONFIG_PATH = os.getenv("CONFIG_PATH") or "./config/config.yml"

DEFAULT_LOGS_DIR = os.getenv("LOGS_PATH") or "logs"

try:
    CUSTOM_MODELS = json.loads(os.getenv("CUSTOM_MODELS", "[]"))
except json.JSONDecodeError:
    print("\033[93m[WARNING] Passed CUSTOM_MODELS env var could not be parsed into JSON\033[0m")
    CUSTOM_MODELS = []

SUPPORTED_REASONER_PROVIDERS = ["groq", "openrouter", "nvidia"]

SUPPORTED_REASONER_MODELS = [
    "deepseek-r1-distill-llama-70b", 
    "deepseek-ai/deepseek-r1",
    "deepseek/deepseek-r1:free"
]

REASONING_START_TOKEN = "<think>"

REASONING_STOP_TOKEN = "</think>"

STREAM_START_TOKEN = "<start>"

STREAM_END_TOKEN = "</end>"

SPECIAL_TOKENS = [
    REASONING_START_TOKEN,
    REASONING_STOP_TOKEN,
    STREAM_START_TOKEN,
    STREAM_END_TOKEN
]

DEFAULT_ENCODING = "utf8"

# Tenacity constants
DEFAULT_MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "0")) or 5
DEFAULT_WAIT_MIN = int(os.getenv("WAIT_MIN", "0")) or 1
DEFAULT_WAIT_MAX = int(os.getenv("WAIT_MAX", "0")) or 60
DEFAULT_WAIT_EXP_MULTIPLIER = int(os.getenv("WAIT_EXP_MULTIPLIER", "0")) or 1

# Observability constants
DEFAULT_OBSERVABILITY_DIR = os.getenv("OBSERVABILITY_DIR") or "observability_data"
DEFAULT_OBSERVABILITY_FILE = os.getenv("OBSERVABILITY_FILE") or "llm_operations.json"