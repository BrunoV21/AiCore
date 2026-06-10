from typing import Dict
from typing_extensions import Self
import traceback

from pydantic import model_validator

from aicore.llm.providers.anthropic import AnthropicLlm

class OllamaLlm(AnthropicLlm):
    base_url :str="https://ollama.com"
    _skip_model_valiation :bool=True

    @model_validator(mode="after")
    def set_extra_headers(self)->Self:
        if not hasattr(self.config, "extra_headers"):
            self.config.extra_headers = self._get_default_ollama_bearer_headers()
        else:
            self.config.extra_headers.update(self._get_default_ollama_bearer_headers())

        self._handle_thinking_models()
        self._pass_fake_tokenizer()

        return self

    def _get_default_ollama_bearer_headers(self)->Dict[str, str]:
        return {'Authorization': 'Bearer ' + self.config.api_key}
    
    @staticmethod
    def fake_tokenizer(contents :str):
        try:
            total_words = len(contents.split(" "))
        except Exception:
            print(traceback.format_exc())
            total_words = len(contents)
        return [_ for _ in range(int(1.5*total_words))]

    def _pass_fake_tokenizer(self):
        self.tokenizer_fn = self.fake_tokenizer

