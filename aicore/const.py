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