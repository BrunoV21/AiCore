from pydantic import BaseModel, RootModel, model_validator
from typing import Union, Optional, Callable, List, Dict, Self
from functools import partial
from pathlib import Path
from enum import Enum
from ulid import ulid

from aicore.llm.config import LlmConfig
from aicore.logger import _logger
from aicore.const import REASONING_STOP_TOKEN
from aicore.llm.templates import REASONING_INJECTION_TEMPLATE
from aicore.llm.utils import default_stream_handler
from aicore.llm.providers import (
    LlmBaseProvider,
    OpenAiLlm,
    MistralLlm, 
    NvidiaLlm,
    GroqLlm,
    GeminiLlm
)

class Providers(Enum):
    OPENAI = OpenAiLlm
    MISTRAL = MistralLlm
    NVIDIA = NvidiaLlm
    GROQ = GroqLlm
    GEMINI = GeminiLlm

    def get_instance(self, config: LlmConfig) -> LlmBaseProvider:
        """
        Instantiate the provider associated with the enum.
        
        Args:
            config (EmbeddingsConfig): Configuration for the provider.
        
        Returns:
            LlmBaseProvider: An instance of the embedding provider.
        """
        return self.value.from_config(config)

class Llm(BaseModel):
    config :LlmConfig
    _provider :Union[LlmBaseProvider, None]=None
    _logger_fn :Optional[Callable[[str], None]]=None
    _session_id :Optional[str]=None
    _reasoner :Union["Llm", None]=None
    
    @property
    def provider(self)->LlmBaseProvider:
        return self._provider
    
    @provider.setter
    def provider(self, provider :LlmBaseProvider):
        self._provider = provider

    @property
    def session_id(self)->str:
        return self._session_id
    
    @session_id.setter
    def session_id(self, session_id):
        self._session_id = session_id

    @property
    def logger_fn(self)->Callable[[str], None]:
        if self._logger_fn is None:
            if self.session_id is None:
                self.session_id = ulid()
            self._logger_fn = partial(_logger.log_chunk_to_queue, session_id=self.session_id)
        return self._logger_fn

    @logger_fn.setter
    def logger_fn(self, logger_fn:Callable[[str], None]):
        self._logger_fn = logger_fn

    @property
    def reasoner(self)->"Llm":
        return self._reasoner
    
    @reasoner.setter
    def reasoner(self, reasoning_llm :"Llm"):
        self._reasoner = reasoning_llm
        if self.session_id:
            self._reasoner.session_id = self.session_id
        self._reasoner.provider.use_as_reasoner()
    
    @model_validator(mode="after")
    def start_provider(self)->Self:
        self.provider = Providers[self.config.provider.upper()].get_instance(self.config)
        if self.config.reasoner:
            self.reasoner = Llm.from_config(self.config.reasoner)
        return self
    
    @classmethod
    def from_config(cls, config :LlmConfig)->"Llm":
        return cls(config=config)
    
    @property
    def tokenizer(self):
        return self.provider.tokenizer_fn
    
    def complete(self,
                 prompt :Union[str, BaseModel, RootModel], 
                 system_prompt :Optional[str]=None,
                 prefix_prompt :Optional[str]=None,
                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                 json_output :bool=False,
                 stream :bool=True)->Union[str, Dict]:

        if self.reasoner:
            if len(self.tokenizer(system_prompt if system_prompt else "" + prompt)) <= self.reasoner.config.max_tokens:
                reasoning = self.reasoner.provider.complete(prompt, None, prefix_prompt, img_path, False, stream)
                default_stream_handler(f"{REASONING_STOP_TOKEN}\n")
                prompt = REASONING_INJECTION_TEMPLATE.format(reasoning=reasoning, prompt=prompt, reasoning_stop_token=REASONING_STOP_TOKEN)

        return self.provider.complete(prompt, system_prompt, prefix_prompt, img_path, json_output, stream)
    
    async def acomplete(self,
                 prompt :Union[str, BaseModel, RootModel],
                 system_prompt :Optional[str]=None,
                 prefix_prompt :Optional[str]=None,
                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                 json_output :bool=False,
                 stream :bool=True)->Union[str, Dict]:
         
        if self.reasoner:
            if len(self.tokenizer(system_prompt if system_prompt else "" + prompt)) <= self.reasoner.config.max_tokens:
                reasoning = await self.reasoner.provider.acomplete(prompt, None, prefix_prompt, img_path, False, stream, self.logger_fn)
                await self.logger_fn(f"{REASONING_STOP_TOKEN}\n")
                prompt = REASONING_INJECTION_TEMPLATE.format(reasoning=reasoning, prompt=prompt, reasoning_stop_token=REASONING_STOP_TOKEN)
        
        return await self.provider.acomplete(prompt, system_prompt, prefix_prompt, img_path, json_output, stream, self.logger_fn)