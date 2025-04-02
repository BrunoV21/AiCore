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
    ANTHROPIC: AnthropicLlm = AnthropicLlm
    OPENAI: OpenAiLlm = OpenAiLlm
    OPENROUTER: OpenRouterLlm = OpenRouterLlm
    MISTRAL: MistralLlm = MistralLlm
    NVIDIA: NvidiaLlm = NvidiaLlm
    GROQ: GroqLlm = GroqLlm
    GEMINI: GeminiLlm = GeminiLlm

    def get_instance(self, config: LlmConfig) -> LlmBaseProvider:
        """
        Instantiate the provider associated with the enum.

        Args:
            config (LlmConfig): Configuration for the provider.

        Returns:
            LlmBaseProvider: An instance of the embedding provider.
        """
        return self.value.from_config(config)

class Llm(BaseModel):
    """
    Llm class provides a unified interface for handling language model operations,
    including synchronous and asynchronous completions, and optional reasoning augmentation.
    It manages the underlying provider, session and workspace identifiers, logging functionality,
    and usage tracking.
    """
    config: LlmConfig
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    agent_id: Optional[str] = None
    _provider: Union[LlmBaseProvider, None] = None
    _logger_fn: Optional[Callable[[str], None]] = None
    _reasoner: Union["Llm", None] = None
    _is_reasoner: bool = False

    @property
    def provider(self) -> LlmBaseProvider:
        """
        Get the underlying LLM provider instance.

        Returns:
            LlmBaseProvider: The underlying provider for LLM operations.
        """
        return self._provider

    @provider.setter
    def provider(self, provider: LlmBaseProvider):
        """
        Set the underlying LLM provider instance.

        Args:
            provider (LlmBaseProvider): The provider to set.
        """
        self._provider = provider

    @computed_field
    def session_id(self) -> str:
        """
        Retrieve the session identifier from the underlying provider.

        Returns:
            str: The session ID.
        """
        return self.provider.session_id

    @session_id.setter
    def session_id(self, value: str):
        """
        Set the session identifier in both this instance and its underlying provider.

        Args:
            value (str): The session ID to set.
        """
        if value:
            self.provider.session_id = value
            if isinstance(self._logger_fn, Logger):
                self._logger_fn = partial(_logger.log_chunk_to_queue, session_id=value)

    @computed_field
    def workspace(self) -> Optional[str]:
        """
        Get the workspace identifier from the underlying provider.

        Returns:
            Optional[str]: The workspace identifier.
        """
        return self.provider.worspace

    @workspace.setter
    def workspace(self, workspace):
        """
        Set the workspace identifier in the underlying provider.

        Args:
            workspace: The workspace value to set.
        """
        self.provider.workspace = workspace

    @property
    def logger_fn(self) -> Callable[[str], None]:
        """
        Retrieve the callable logger function for output logging in this session.

        Returns:
            Callable[[str], None]: A function to log messages.
        """
        if self._logger_fn is None:
            if self.session_id is None:
                self.session_id = ulid()
                if self.reasoner:
                    self.reasoner.session_id = self.session_id
            self._logger_fn = partial(_logger.log_chunk_to_queue, session_id=self.session_id)
        return self._logger_fn

    @logger_fn.setter
    def logger_fn(self, logger_fn: Callable[[str], None]):
        """
        Set the logger function.

        Args:
            logger_fn (Callable[[str], None]): A callable function to log messages.
        """
        self._logger_fn = logger_fn

    @property
    def reasoner(self) -> "Llm":
        """
        Get the associated reasoner LLM instance used for augmenting responses.

        Returns:
            Llm: The reasoner LLM instance, or None if not set.
        """
        return self._reasoner

    @reasoner.setter
    def reasoner(self, reasoning_llm: "Llm"):
        """
        Set the reasoner LLM instance and configure it for reasoning operations.

        Args:
            reasoning_llm (Llm): An Llm instance to be used as the reasoner.
        """
        self._reasoner = reasoning_llm
        self._reasoner.system_prompt = REASONER_DEFAULT_SYSTEM_PROMPT
        self._reasoner.provider.use_as_reasoner(self.session_id, self.workspace)

    @model_validator(mode="after")
    def start_provider(self) -> Self:
        """
        Initialize the underlying provider based on the configuration and,
        if applicable, initialize the reasoner.

        Returns:
            Self: The current Llm instance with the provider started.
        """
        self.provider = Providers[self.config.provider.upper()].get_instance(self.config)
        if self.config.reasoner:
            self.reasoner = Llm.from_config(self.config.reasoner)
        return self

    @classmethod
    def from_config(cls, config: LlmConfig) -> "Llm":
        """
        Create an Llm instance from the given configuration.

        Args:
            config (LlmConfig): The configuration to use for creating the instance.

        Returns:
            Llm: A new Llm instance.
        """
        return cls(config=config)

    @property
    def tokenizer(self):
        """
        Retrieve the tokenizer function from the underlying provider.

        Returns:
            Callable: A function that tokenizes input text.
        """
        return self.provider.tokenizer_fn

    @computed_field
    def usage(self) -> UsageInfo:
        """
        Retrieve usage metrics collected from LLM operations.

        Returns:
            UsageInfo: Contains token counts and cost metrics.
        """
        return self.provider.usage

    @staticmethod
    def _include_reasoning_as_prefix(prefix_prompt: Union[str, List[str], None], reasoning: str) -> List[str]:
        """
        Append a reasoning string to the existing prefix prompt.

        Args:
            prefix_prompt (Union[str, List[str], None]): The original prefix prompt.
            reasoning (str): The reasoning text to inject.

        Returns:
            List[str]: The updated list of prefix prompt segments.
        """
        if not prefix_prompt:
            prefix_prompt = []
        elif isinstance(prefix_prompt, str):
            prefix_prompt = [prefix_prompt]
        prefix_prompt.append(reasoning)
        return prefix_prompt

    def _reason(
        self,
        prompt: Union[str, BaseModel, RootModel],
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
        stream: bool = True,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None
    ) -> List[str]:
        """
        Generate and include a reasoning prefix from the reasoner, if configured.

        Args:
            prompt (Union[str, BaseModel, RootModel]): The primary prompt for completion.
            system_prompt (Optional[Union[str, List[str]]]): Override system prompt if provided.
            prefix_prompt (Optional[Union[str, List[str]]]): Existing prompt prefix.
            img_path (Optional[Union[str, Path, List[Union[str, Path]]]]): Optional image paths.
            stream (bool): Flag indicating whether the response is streamed.
            agent_id (Optional[str]): Optional agent identifier.
            action_id (Optional[str]): Optional action identifier.

        Returns:
            List[str]: The prefix prompt updated with the reasoning.
        """
        if self.reasoner:
            system_prompt = system_prompt or self.reasoner.system_prompt
            reasoning = self.reasoner.provider.complete(prompt, system_prompt, prefix_prompt, img_path, False, stream, agent_id, action_id)
            reasoning_msg = REASONING_INJECTION_TEMPLATE.format(reasoning=reasoning, reasoning_stop_token=REASONING_STOP_TOKEN)
            prefix_prompt = self._include_reasoning_as_prefix(prefix_prompt, reasoning_msg)
        return prefix_prompt

    async def _areason(
        self,
        prompt: Union[str, BaseModel, RootModel],
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
        stream: bool = True,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None
    ) -> List[str]:
        """
        Asynchronously generate and include a reasoning prefix from the reasoner, if present.

        Args:
            prompt (Union[str, BaseModel, RootModel]): The input prompt.
            system_prompt (Optional[Union[str, List[str]]]): Optional override for the system prompt.
            prefix_prompt (Optional[Union[str, List[str]]]): Pre-existing prompt prefix.
            img_path (Optional[Union[str, Path, List[Union[str, Path]]]]): Optional image paths.
            stream (bool): Whether streaming mode is enabled.
            agent_id (Optional[str]): Optional agent identifier.
            action_id (Optional[str]): Optional action identifier.

        Returns:
            List[str]: The updated prefix prompt including the injected reasoning.
        """
        if self.reasoner:
            sys_prompt = system_prompt or self.reasoner.system_prompt
            reasoning = await self.reasoner.provider.acomplete(prompt, sys_prompt, prefix_prompt, img_path, False, stream, self.logger_fn, agent_id, action_id)
            reasoning_msg = REASONING_INJECTION_TEMPLATE.format(reasoning=reasoning, reasoning_stop_token=REASONING_STOP_TOKEN)
            prefix_prompt = self._include_reasoning_as_prefix(prefix_prompt, reasoning_msg)
        return prefix_prompt

    @retry_on_rate_limit
    def complete(
        self,
        prompt: Union[str, BaseModel, RootModel],
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
        json_output: bool = False,
        stream: bool = True,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None
    ) -> Union[str, Dict]:
        """
        Handle synchronous completion requests.

        This method orchestrates prompt preparation, optional reasoning injection, and calls the underlying provider to generate a completion.

        Args:
            prompt (Union[str, BaseModel, RootModel]): The input prompt.
            system_prompt (Optional[Union[str, List[str]]]): Optional system prompt override; defaults to the instance's system_prompt.
            prefix_prompt (Optional[Union[str, List[str]]]): An optional prefix for the prompt; may include reasoning.
            img_path (Optional[Union[str, Path, List[Union[str, Path]]]]): Optional image path(s) for multimodal input.
            json_output (bool): If True, the output is parsed as JSON.
            stream (bool): Whether the output is streamed.
            agent_id (Optional[str]): Optional agent identifier.
            action_id (Optional[str]): Optional action identifier.

        Returns:
            Union[str, Dict]: The completion result, either as a raw string or as a parsed dictionary.
        """
        sys_prompt = system_prompt or self.system_prompt
        prefix_prompt = self._reason(prompt, None, prefix_prompt, img_path, stream, agent_id, action_id)
        return self.provider.complete(prompt, sys_prompt, prefix_prompt, img_path, json_output, stream, agent_id, action_id)

    @retry_on_rate_limit
    async def acomplete(
        self,
        prompt: Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel],
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
        json_output: bool = False,
        stream: bool = True,
        agent_id: Optional[str] = None,
        action_id: Optional[str] = None
    ) -> Union[str, Dict]:
        """
        Handle asynchronous completion requests.

        This method asynchronously prepares the prompt (injecting reasoning if configured)
        and retrieves the completion from the underlying provider.

        Args:
            prompt (Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel]): The input prompt.
            system_prompt (Optional[Union[str, List[str]]]): Optional system prompt override.
            prefix_prompt (Optional[Union[str, List[str]]]): An optional prefix prompt, which may include reasoning.
            img_path (Optional[Union[str, Path, List[Union[str, Path]]]]): Optional image path(s) for multimodal requests.
            json_output (bool): If True, parse and return the output as JSON.
            stream (bool): If True, process the response as a stream.
            agent_id (Optional[str]): Optional agent identifier.
            action_id (Optional[str]): Optional action identifier.

        Returns:
            Union[str, Dict]: The asynchronous completion result, either as a string or a parsed dictionary.
        """
        sys_prompt = system_prompt or self.system_prompt
        prefix_prompt = await self._areason(prompt, None, prefix_prompt, img_path, stream, agent_id, action_id)
        return await self.provider.acomplete(prompt, sys_prompt, prefix_prompt, img_path, json_output, stream, self.logger_fn, agent_id, action_id)
