import os

DEFAULT_CONFIG_PATH = os.getenv("CONFIG_PATH") or "./config/config.yml"

DEFAULT_LOGS_DIR = os.getenv("LOGS_PATH") or "logs"

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

DEFAULT_ENCODING = "utf8"

# Tenacity constants
DEFAULT_MAX_ATTEMPTS = os.getenv("MAX_ATTEMPTS") or 5
DEFAULT_WAIT_MIN = os.getenv("WAIT_MIN") or 1
DEFAULT_WAIT_MAX = os.getenv("WAIT_MAX") or 60
DEFAULT_WAIT_EXP_MULTIPLIER = os.getenv("WAIT_EXP_MULTIPLIER") or 1

# Observability constants
DEFAULT_OBSERVABILITY_DIR = os.getenv("OBSERVABILITY_DIR") or "observability_data"
DEFAULT_OBSERVABILITY_FILE = os.getenv("OBSERVABILITY_FILE") or "llm_operations.json"
DEFAULT_DASHBOARD_PORT = os.getenv("DASHBOARD_PORT") or 8050
DEFAULT_DASHBOARD_HOST = os.getenv("DASHBOARD_HOST") or "127.0.0.1"