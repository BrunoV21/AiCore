from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.models import AuthenticationError
from pydantic import model_validator
from groq import Groq, AsyncGroq, AuthenticationError
from groq.types.chat import ChatCompletionChunk
from typing import Optional
from typing_extensions import Self
import tiktoken

class GroqLlm(LlmBaseProvider):

    @model_validator(mode="after")
    def set_groq(self)->Self:

        self.client :Groq = Groq(
            api_key=self.config.api_key
        )
        self._auth_exception = AuthenticationError
        self.validate_config()
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
    
    def normalize(self, chunk :ChatCompletionChunk, completion_id :Optional[str]=None):
        x_usage = chunk.x_groq
        if x_usage is not None and x_usage.usage is not None:
            self.usage.record_completion(
                prompt_tokens=x_usage.usage.prompt_tokens,
                response_tokens=x_usage.usage.completion_tokens,
                completion_id=completion_id or chunk.id
            )
        return chunk.choices