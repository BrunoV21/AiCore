from typing import Dict
from typing_extensions import Self

from pydantic import model_validator

from aicore.llm.providers.anthropic import AnthropicLlm

class OllamaLlm(AnthropicLlm):
    _skip_validation :bool=True
    base_url :str="https://ollama.com"

    @model_validator(mode="after")
    def set_extra_headers(self)->Self:
        if not hasattr(self.config, "extra_headers"):
            self.config.extra_headers = self._get_default_ollama_bearer_headers()
        else:
            self.config.extra_headers.update(self._get_default_ollama_bearer_headers())

        self._handle_thinking_models()
        return self

    def _get_default_ollama_bearer_headers(self)->Dict[str, str]:
        return {'Authorization': 'Bearer ' + self.config.api_key}

