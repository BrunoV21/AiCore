
DEFAULT_CONFIG_PATH = "./config/config.yml"

DEFAULT_LOGS_DIR = "logs"

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

# Observability constants
DEFAULT_OBSERVABILITY_DIR = "observability_data"
DEFAULT_OBSERVABILITY_FILE = "llm_operations.json"
DEFAULT_DASHBOARD_PORT = 8050
DEFAULT_DASHBOARD_HOST = "127.0.0.1"

# Operation types for tracking
OPERATION_TYPE_COMPLETION = "completion"
OPERATION_TYPE_ACOMPLETION = "acompletion"

# Maximum length for stored response text
MAX_STORED_RESPONSE_LENGTH = 1000