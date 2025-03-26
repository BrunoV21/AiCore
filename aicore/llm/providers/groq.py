from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.models import AuthenticationError
from pydantic import model_validator
from groq import Groq, AsyncGroq, AuthenticationError
from groq.types.chat import ChatCompletion
from typing import Self, Optional
import tiktoken

class GroqLlm(LlmBaseProvider):

    @model_validator(mode="after")
    def set_groq(self)->Self:

        self.client :Groq = Groq(
            api_key=self.config.api_key
        )
        self.validate_config(AuthenticationError)
        _aclient = AsyncGroq(
            api_key=self.config.api_key
        )
        self.aclient :AsyncGroq = _aclient

        self.completion_fn = self.client.chat.completions.create
        self.acompletion_fn = _aclient.chat.completions.create

        self.normalize_fn = self.normalize

        self.tokenizer_fn = tiktoken.encoding_for_model(
            self.get_default_tokenizer(
                self.config.model
            )
        ).encode

        return self
    
    def normalize(self, chunk :ChatCompletion, completion_id :Optional[str]=None):
        usage = chunk.usage
        if usage is not None:
            self.usage.record_completion(
                prompt_tokens=usage.prompt_tokens,
                response_tokens=usage.completion_tokens,
                completion_id=completion_id or chunk.id
            )
        return chunk.choices