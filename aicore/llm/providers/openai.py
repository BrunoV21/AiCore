from aicore.llm.providers.base_provider import LlmBaseProvider
from pydantic import model_validator
from openai import OpenAI, AsyncOpenAI, AuthenticationError
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
        self.validate_config(AuthenticationError)
        self.aclient = _aclient
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

        self._handle_reasoning_models()

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
    
    def _handle_reasoning_models(self):
        ### o series models
        if self.config.model.startswith("o"):
            self.completion_args["temperature"] = None
            self.completion_args["max_tokens"] = None
            self.completion_args["max_completion_tokens"] = self.config.max_tokens
            reasoning_efftort = getattr(self.config, "reasoning_efftort", None)
            if reasoning_efftort is not None:
                self.completion_args["reasoning_efftort"] = reasoning_efftort