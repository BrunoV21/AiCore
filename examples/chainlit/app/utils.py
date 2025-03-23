from pathlib import Path
from typing import Optional
import openai
import os

CONFIG_DIR = Path("./config")

REASONER_PROVIDERS_MAP = {
    "deepseek-r1-distill-llama-70b": "groq",
    "deepseek-ai/deepseek-r1": "nvidia",
    "deepseek/deepseek-r1:free": "openrouter"
}

MODELS_PROVIDERS_MAP = {
    "mistral-small-latest": "mistral",
    "open-mistral-nemo": "mistral",
    "mistral-large-latest": "mistral",
    "gemini-2.0-flash-exp": "gemini",
    "gemma2-9b-it": "groq",
    "llama-3.3-70b-versatile": "groq",
    "llama-3.2-3b-preview": "groq"
}

PROVIDERS_API_KEYS = {
    "gemini": os.environ.get("GEMINI_API_KEY"),
    "groq": os.environ.get("GROQ_API_KEY"),
    "mistral": os.environ.get("MISTRAL_API_KEY"),
    "nvidia": os.environ.get("NVIDIA_API_KEY"),
    "openrouter": os.environ.get("OPENROUTER_API_KEY")
}

def check_openai_api_key(api_key, base_url=None):
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    try:
        client.models.list()
    except openai.AuthenticationError:
        return False
    else:
        return True

def trim_messages(messages, tokenizer_fn, max_tokens :Optional[int]=None):
    max_tokens = max_tokens or int(os.environ.get("MAX_HISTORY_TOKENS", 1028))
    while messages and sum(len(tokenizer_fn(msg)) for msg in messages) > max_tokens:
        messages.pop(0)  # Remove from the beginning
    return messages