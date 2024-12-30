from aicore.llm.providers.base_provider import BaseProvider
from pydantic import model_validator
from openai import OpenAI, AsyncOpenAI
from typing import Self

class OpenAiLlm(BaseProvider):

    @model_validator(mode="after")
    def set_openai(self)->Self:

        self.client :OpenAI = OpenAI(
            api_key=self.config.api_key
        )
        self.aclient :AsyncOpenAI = AsyncOpenAI(
            api_key=self.config.api_key
        )
        self.completion_fn = self.client.chat.completions.create
        self.acompletion_fn = self.aclient.chat.completions.create
        self.completion_args["stream_options"] = {
            "include_usage": True
        }
        self.normalize_fn = self.normalize

        return self
    
    def normalize(self, chunk):
        return chunk.choices    