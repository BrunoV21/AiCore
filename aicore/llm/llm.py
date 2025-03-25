from pydantic import BaseModel, RootModel, model_validator, computed_field
from typing import Union, Optional, Callable, List, Dict, Self
from functools import partial
from pathlib import Path
from enum import Enum
from ulid import ulid

from aicore.logger import _logger, Logger
from aicore.utils import retry_on_rate_limit
from aicore.const import REASONING_STOP_TOKEN
from aicore.llm.usage import UsageInfo
from aicore.llm.config import LlmConfig
from aicore.llm.templates import REASONING_INJECTION_TEMPLATE, DEFAULT_SYSTEM_PROMPT, REASONER_DEFAULT_SYSTEM_PROMPT
from aicore.llm.providers import (
    LlmBaseProvider,
    AnthropicLlm,
    OpenAiLlm,
    OpenRouterLlm,
    MistralLlm, 
    NvidiaLlm,
    GroqLlm,
    GeminiLlm
)

class Providers(Enum):
    ANTHROPIC :AnthropicLlm=AnthropicLlm
    OPENAI :OpenAiLlm=OpenAiLlm
    OPENROUTER :OpenRouterLlm=OpenRouterLlm
    MISTRAL :MistralLlm=MistralLlm
    NVIDIA :NvidiaLlm=NvidiaLlm
    GROQ :GroqLlm=GroqLlm
    GEMINI :GeminiLlm=GeminiLlm

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
    system_prompt :str=DEFAULT_SYSTEM_PROMPT
    agent_id :Optional[str]=None
    _provider :Union[LlmBaseProvider, None]=None
    _logger_fn :Optional[Callable[[str], None]]=None
    _reasoner :Union["Llm", None]=None
    _is_reasoner :bool=False
    
    @property
    def provider(self)->LlmBaseProvider:
        return self._provider
    
    @provider.setter
    def provider(self, provider :LlmBaseProvider):
        self._provider = provider

    @computed_field
    def session_id(self)->str:
        return self.provider.session_id
    
    @session_id.setter
    def session_id(self, value :str):
        if value:
            self.provider.session_id = value
            if isinstance(self._logger_fn, Logger):
                self._logger_fn = partial(_logger.log_chunk_to_queue, session_id=value)

    @computed_field
    def workspace(self)->Optional[str]:
        return self.provider.worspace
    
    @workspace.setter
    def workspace(self, workspace):
        self.provider.workspace = workspace

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
        self._reasoner.system_prompt = REASONER_DEFAULT_SYSTEM_PROMPT
        self._reasoner.provider.use_as_reasoner(self.session_id, self.workspace)
    
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
    
    @computed_field
    def usage(self)->UsageInfo:
        return self.provider.usage
    
    @staticmethod
    def _include_reasoning_as_prefix(prefix_prompt :Union[str, List[str], None], reasoning :str)->List[str]:
        if not prefix_prompt:
            prefix_prompt = []
        elif isinstance(prefix_prompt, str):
            prefix_prompt = [prefix_prompt]
        prefix_prompt.append(reasoning)
        return prefix_prompt
    
    def _reason(self, 
            prompt :Union[str, BaseModel, RootModel],
            system_prompt :Optional[Union[str, List[str]]]=None,
            prefix_prompt :Optional[Union[str, List[str]]]=None,
            img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
            stream :bool=True, agent_id: Optional[str]=None, action_id :Optional[str]=None)->List[str]:
        
        if self.reasoner:
            system_prompt = system_prompt or self.reasoner.system_prompt
            reasoning = self.reasoner.provider.complete(prompt, system_prompt, prefix_prompt, img_path, False, stream, agent_id, action_id)
            reasoning_msg = REASONING_INJECTION_TEMPLATE.format(reasoning=reasoning, reasoning_stop_token=REASONING_STOP_TOKEN)
            prefix_prompt = self._include_reasoning_as_prefix(prefix_prompt, reasoning_msg)
            
        return prefix_prompt
    
    async def _areason(self, 
        prompt :Union[str, BaseModel, RootModel],
        system_prompt :Optional[Union[str, List[str]]]=None,
        prefix_prompt :Optional[Union[str, List[str]]]=None,
        img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
        stream :bool=True, agent_id: Optional[str]=None, action_id :Optional[str]=None)->List[str]:
        
        if self.reasoner:
            sys_prompt = system_prompt or self.reasoner.system_prompt
            reasoning = await self.reasoner.provider.acomplete(prompt, sys_prompt, prefix_prompt, img_path, False, stream, self.logger_fn, agent_id, action_id)
            reasoning_msg = REASONING_INJECTION_TEMPLATE.format(reasoning=reasoning, reasoning_stop_token=REASONING_STOP_TOKEN)
            prefix_prompt = self._include_reasoning_as_prefix(prefix_prompt, reasoning_msg)            
        return prefix_prompt
    
    @retry_on_rate_limit
    def complete(self,
                 prompt :Union[str, BaseModel, RootModel],
                 system_prompt :Optional[Union[str, List[str]]]=None,
                 prefix_prompt :Optional[Union[str, List[str]]]=None,
                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                 json_output :bool=False,
                 stream :bool=True,
                 agent_id :Optional[str]=None,
                 action_id :Optional[str]=None)->Union[str, Dict]:
        
        """
        msg can be a simple str, list of str (mapped to answer-questions pairs from the latest) or list completion like dicts
        """

        sys_prompt = system_prompt or self.system_prompt
        prefix_prompt = self._reason(prompt, None, prefix_prompt, img_path, stream, agent_id, action_id)
        return self.provider.complete(prompt, sys_prompt, prefix_prompt, img_path, json_output, stream, agent_id, action_id)
    
    @retry_on_rate_limit
    async def acomplete(self,
                 prompt :Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel],
                 system_prompt :Optional[Union[str, List[str]]]=None,
                 prefix_prompt :Optional[Union[str, List[str]]]=None,
                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                 json_output :bool=False,
                 stream :bool=True,
                 agent_id :Optional[str]=None,
                 action_id :Optional[str]=None)->Union[str, Dict]:
        """
        msg can be a simple str, list of str (mapped to answer-questions pairs from the latest) or list completion like dicts
        """
         
        sys_prompt = system_prompt or self.system_prompt
        prefix_prompt = await self._areason(prompt, None, prefix_prompt, img_path, stream, agent_id, action_id)
        return await self.provider.acomplete(prompt, sys_prompt, prefix_prompt, img_path, json_output, stream, self.logger_fn, agent_id, action_id)