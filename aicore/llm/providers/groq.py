from aicore.llm.providers.base_provider import LlmBaseProvider
from pydantic import model_validator
from groq import Groq, AsyncGroq
from typing import Self
import tiktoken

class GroqLlm(LlmBaseProvider):

    @model_validator(mode="after")
    def set_groq(self)->Self:

        self.client :Groq = Groq(
            api_key=self.config.api_key
        )

        self.aclient :AsyncGroq = AsyncGroq(
            api_key=self.config.api_key
        )

        self.completion_fn = self.client.chat.completions.create
        self.acompletion_fn = self.aclient.chat.completions.create

        self.normalize_fn = self.normalize

        self.tokenizer_fn = tiktoken.encoding_for_model(
            self.get_default_tokenizer(
                self.config.model
            )
        ).encode

        return self
    
    def normalize(self, chunk):
        return chunk.choices