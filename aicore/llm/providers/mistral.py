from aicore.llm.providers.base_provider import BaseProvider
from pydantic import model_validator
from mistralai import Mistral
from typing import Self

class MistralLlm(BaseProvider):

    @model_validator(mode="after")
    def set_mistral(self)->Self:

        self.client :Mistral = Mistral(
            api_key=self.config.api_key
        )
        ### Suspect Misral will always stream by default
        self.completion_fn = self.client.chat.stream
        self.acompletion_fn = self.client.chat.stream_async
        self.normalize_fn = self.normalize

        return self
    
    def normalize(self, chunk):
        return chunk.data.choices