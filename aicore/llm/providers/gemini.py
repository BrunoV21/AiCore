from aicore.llm.providers.openai import OpenAiLlm
from pydantic import model_validator
from google.genai import Client
from functools import partial
from openai.types.chat import ChatCompletion
from typing import List, Optional
from typing_extensions import Self

class GeminiLlm(OpenAiLlm):
    base_url :str="https://generativelanguage.googleapis.com/v1beta/openai/"

    @staticmethod
    def gemini_count_tokens(contents :str, client :Client, model :str)->List[int]:
        response = client.models.count_tokens(
            contents=contents,
            model=model
        )
        return [i for i in range(response.total_tokens)] if response.total_tokens else []

    @model_validator(mode="after")
    def pass_gemini_tokenizer_fn(self)->Self:
        _client = Client(
            api_key=self.config.api_key
        )
        self.tokenizer_fn = partial(
            self.gemini_count_tokens,
            client=_client,
            model=self.config.model
        )

        return self

    def normalize(self, chunk :ChatCompletion, completion_id :Optional[str]=None):
        usage = chunk.usage
        if usage is not None and usage.completion_tokens:
            return super().normalize(chunk, completion_id)
        return chunk.choices