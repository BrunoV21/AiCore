from aicore.llm.providers.base_provider import LlmBaseProvider
from pydantic import model_validator
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion
from typing import Self, Optional
import tiktoken
class OpenAiLlm(LlmBaseProvider):
    base_url :Optional[str]=None

    @model_validator(mode="after")
    def set_openai(self)->Self:

        self.client :OpenAI = OpenAI(
            api_key=self.config.api_key,
            base_url=self.base_url
        )
        _aclient :AsyncOpenAI = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.base_url
        )
        self.aclient =  _aclient
        self.completion_fn = self.client.chat.completions.create
        self.acompletion_fn = _aclient.chat.completions.create
        self.completion_args["stream_options"] = {
            "include_usage": True
        }
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