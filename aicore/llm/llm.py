from pydantic import BaseModel, Field, RootModel, model_validator, computed_field
from typing import Union, Optional, Callable, List, Dict
from typing_extensions import Self
from functools import partial
from pathlib import Path
from enum import Enum
from ulid import ulid

from aicore.logger import _logger, Logger
from aicore.utils import retry_on_failure, raise_on_balance_error
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
    GeminiLlm,
    DeepSeekLlm,
    GrokLlm
)

class Providers(Enum):
    ANTHROPIC :AnthropicLlm=AnthropicLlm
    OPENAI :OpenAiLlm=OpenAiLlm
    OPENROUTER :OpenRouterLlm=OpenRouterLlm
    MISTRAL :MistralLlm=MistralLlm
    NVIDIA :NvidiaLlm=NvidiaLlm
    GROQ :GroqLlm=GroqLlm
    GROK :GrokLlm=GrokLlm 
    GEMINI :GeminiLlm=GeminiLlm
    DEEPSEEK :DeepSeekLlm=DeepSeekLlm

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
    """Main LLM class that provides synchronous and asynchronous completion interfaces.
    
    Attributes:
        config: Configuration for the LLM provider
        system_prompt: Default system prompt for the LLM
        agent_id: Optional agent identifier
        _provider: Internal provider instance
        _logger_fn: Optional logging function
        _reasoner: Optional reasoning LLM instance
        _is_reasoner: Flag indicating if this is a reasoning LLM
    """
    config: LlmConfig = Field(..., description="Configuration for the LLM provider")
    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT, description="Default system prompt for the LLM")
    agent_id: Optional[str] = Field(default=None, description="Optional agent identifier")
    _provider: Optional[LlmBaseProvider] = None
    _logger_fn: Optional[Callable[[str], None]] = None
    _reasoner: Optional["Llm"] = None
    _is_reasoner: bool = False
    
    @property
    def provider(self)->LlmBaseProvider:
        """Get the current provider instance."""
        return self._provider
    
    @provider.setter
    def provider(self, provider :LlmBaseProvider):
        """Set the provider instance.
        
        Args:
            provider: The LLM provider instance to set
        """
        self._provider = provider

    @computed_field
    def session_id(self)->str:
        """Get the current session ID from the provider."""
        return self.provider.session_id
    
    @session_id.setter
    def session_id(self, value :str):
        """Set the session ID and update logger if needed.
        
        Args:
            value: The session ID to set
        """
        if value:
            self.provider.session_id = value
            if isinstance(self._logger_fn, Logger):
                self._logger_fn = partial(_logger.log_chunk_to_queue, session_id=value)

    @computed_field
    def extras(self)->dict:
        """Get provider extras dictionary."""
        return self.provider.extras
    
    @extras.setter
    def extras(self, value :dict):
        """Set provider extras.
        
        Args:
            value: Dictionary of extra provider settings
        """
        if value and isinstance(value, dict):
            self.provider.extras = value

    @computed_field
    def workspace(self)->Optional[str]:
        """Get the current workspace from the provider."""
        return self.provider.worspace
    
    @workspace.setter
    def workspace(self, workspace):
        """Set the workspace for the provider.
        
        Args:
            workspace: Workspace identifier to set
        """
        self.provider.workspace = workspace

    @property
    def logger_fn(self)->Callable[[str], None]:
        """Get or initialize the logger function.
        
        Returns:
            A logging function bound to the current session
        """
        if self._logger_fn is None:
            if self.session_id is None:
                self.session_id = ulid()
                if self.reasoner:
                    self.reasoner.session_id = self.session_id
            self._logger_fn = partial(_logger.log_chunk_to_queue, session_id=self.session_id)
        return self._logger_fn

    @logger_fn.setter
    def logger_fn(self, logger_fn:Callable[[str], None]):
        """Set a custom logger function.
        
        Args:
            logger_fn: Function that handles log messages
        """
        self._logger_fn = logger_fn

    @property
    def reasoner(self)->"Llm":
        """Get the current reasoner LLM instance."""
        return self._reasoner
    
    @reasoner.setter
    def reasoner(self, reasoning_llm :"Llm"):
        """Set the reasoner LLM instance.
        
        Args:
            reasoning_llm: LLM instance to use for reasoning
        """
        self._reasoner = reasoning_llm
        self._reasoner.system_prompt = REASONER_DEFAULT_SYSTEM_PROMPT
        self._reasoner.provider.use_as_reasoner(self.session_id, self.workspace)
    
    @model_validator(mode="after")
    def start_provider(self)->Self:
        """Initialize the provider after model validation."""
        self.provider = Providers[self.config.provider.upper()].get_instance(self.config)
        if self.config.reasoner:
            self.reasoner = Llm.from_config(self.config.reasoner)
        return self
    
    @classmethod
    def from_config(cls, config :LlmConfig)->"Llm":
        """Create an LLM instance from configuration.
        
        Args:
            config: LLM configuration
            
        Returns:
            Initialized LLM instance
        """
        return cls(config=config)
    
    @property
    def tokenizer(self):
        """Get the tokenizer function from the provider."""
        return self.provider.tokenizer_fn
    
    @computed_field
    def usage(self)->UsageInfo:
        """Get usage information from the provider."""
        return self.provider.usage
    
    @staticmethod
    def _include_reasoning_as_prefix(prefix_prompt :Union[str, List[str], None], reasoning :str)->List[str]:
        """Include reasoning steps as prefix prompts.
        
        Args:
            prefix_prompt: Existing prefix prompts (can be str, list of str, or None)
            reasoning: Reasoning steps to include
            
        Returns:
            Combined prompts with reasoning included
        """
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
        """Generate reasoning steps and include them in prefix prompts.
        
        Args:
            prompt: Input prompt for reasoning
            system_prompt: Optional system prompt override
            prefix_prompt: Existing prefix prompts
            img_path: Optional image path(s) for multimodal input
            stream: Whether to stream the response
            agent_id: Optional agent identifier
            action_id: Optional action identifier
            
        Returns:
            List of prompts with reasoning included
        """
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
        """Async version of _reason to generate reasoning steps.
        
        Args:
            prompt: Input prompt for reasoning
            system_prompt: Optional system prompt override
            prefix_prompt: Existing prefix prompts
            img_path: Optional image path(s) for multimodal input
            stream: Whether to stream the response
            agent_id: Optional agent identifier
            action_id: Optional action identifier
            
        Returns:
            List of prompts with reasoning included
        """
        if self.reasoner:
            sys_prompt = system_prompt or self.reasoner.system_prompt
            reasoning = await self.reasoner.provider.acomplete(prompt, sys_prompt, prefix_prompt, img_path, False, stream, self.logger_fn, agent_id, action_id)
            reasoning_msg = REASONING_INJECTION_TEMPLATE.format(reasoning=reasoning, reasoning_stop_token=REASONING_STOP_TOKEN)
            prefix_prompt = self._include_reasoning_as_prefix(prefix_prompt, reasoning_msg)            
        return prefix_prompt
    
    @retry_on_failure
    @raise_on_balance_error
    def complete(self,
        prompt :Union[str, BaseModel, RootModel],
        system_prompt :Optional[Union[str, List[str]]]=None,
        prefix_prompt :Optional[Union[str, List[str]]]=None,
        img_path :Optional[Union[Union[str, Path, bytes], List[Union[str, Path, bytes]]]]=None,
        json_output :bool=False,
        stream :bool=True,
        agent_id :Optional[str]=None,
        action_id :Optional[str]=None)->Union[str, Dict]:        
        """Complete a prompt using the LLM provider.
            
        Args:
            prompt: Input prompt (can be str, BaseModel, or RootModel)
            system_prompt: Optional system prompt override
            prefix_prompt: Additional context to prepend
            img_path: Optional image path(s) for multimodal input
            json_output: Whether to parse output as JSON
            stream: Whether to stream the response
            agent_id: Optional agent identifier
            action_id: Optional action identifier
            
        Returns:
            The completion result as either a string or dictionary (if json_output=True)
                
        Example:
            >>> llm = Llm(config=LlmConfig(provider="openai", api_key="...", model="gpt-4"))
            >>> response = llm.complete("Hello world")
            >>> print(response)
        """

        sys_prompt = system_prompt or self.system_prompt
        prefix_prompt = self._reason(prompt, None, prefix_prompt, img_path, stream, agent_id, action_id)
        return self.provider.complete(prompt, sys_prompt, prefix_prompt, img_path, json_output, stream, agent_id, action_id)
    
    @retry_on_failure
    @raise_on_balance_error
    async def acomplete(self,
                 prompt :Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel],
                 system_prompt :Optional[Union[str, List[str]]]=None,
                 prefix_prompt :Optional[Union[str, List[str]]]=None,
                 img_path :Optional[Union[Union[str, Path, bytes], List[Union[str, Path, bytes]]]]=None,
                 json_output :bool=False,
                 stream :bool=True,
                 as_message_records :bool=False,
                 agent_id :Optional[str]=None,
                 action_id :Optional[str]=None) -> Union[str, Dict, List[Union[str, Dict[str, str]]]]:
        """Async version of complete() to generate completions.
        
        Args:
            prompt: Input prompt (can be str, list, dict, BaseModel or RootModel)
            system_prompt: Optional system prompt override
            prefix_prompt: Additional context to prepend
            img_path: Optional image path(s) for multimodal input
            json_output: Whether to parse output as JSON
            stream: Whether to stream the response
            agent_id: Optional agent identifier
            action_id: Optional ac*tion identifier
            
        Returns:
            The completion result as either a string or dictionary (if json_output=True)

        Example:
            >>> llm = Llm(config=LlmConfig(provider="openai", api_key="...", model="gpt-4"))
            >>> response = await llm.acomplete("Hello world")
            >>> print(response)
        """
         
        sys_prompt = system_prompt or self.system_prompt
        prefix_prompt = await self._areason(prompt, None, prefix_prompt, img_path, stream, agent_id, action_id)
        return await self.provider.acomplete(prompt, sys_prompt, prefix_prompt, img_path, json_output, stream, as_message_records, self.logger_fn, agent_id, action_id)