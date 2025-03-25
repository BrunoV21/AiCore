
"""
AI Core: A unified interface for LLM and embedding providers.

This library provides a consistent API for working with various LLM providers
(OpenAI, Mistral, Groq, Gemini, Nvidia, OpenRouter) and embedding providers,
with support for both synchronous and asynchronous operations.
"""

from aicore.config import Config
from aicore.llm import Llm, LlmConfig
from aicore.embeddings import Embeddings, EmbeddingsConfig
from aicore.logger import Logger, _logger

__all__ = [
    "Config",
    "Llm",
    "LlmConfig",
    "Embeddings",
    "EmbeddingsConfig",
    "Logger"
]

__version__ = "0.1.9"