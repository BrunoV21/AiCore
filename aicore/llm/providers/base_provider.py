"""
Base provider class for LLM implementations with common functionality.
This module defines the base class for all LLM providers in the system, providing
common interfaces and utilities for synchronous and asynchronous operations.
"""

from aicore.llm.config import LlmConfig
from aicore.logger import _logger, default_stream_handler
from aicore.const import REASONING_START_TOKEN, REASONING_STOP_TOKEN, STREAM_START_TOKEN, STREAM_END_TOKEN, CUSTOM_MODELS
from aicore.llm.utils import parse_content, image_to_base64
from aicore.llm.usage import UsageInfo
from aicore.models import AuthenticationError, ModelError
from aicore.observability.collector import LlmOperationCollector
from typing import Any, Dict, Optional, Literal, List, Union, Callable
from pydantic import BaseModel, RootModel, Field
from functools import partial, wraps
from pathlib import Path
import tiktoken
import json
import time
import ulid

class LlmBaseProvider(BaseModel):    
    """Base class for all LLM provider implementations.
    
    Provides common functionality for:
    - Configuration management
    - Session tracking
    - Synchronous and asynchronous completions
    - Streaming support
    - Observability integration
    - Usage tracking
    
    Attributes:
        config: Configuration for the LLM provider
        session_id: Unique session identifier
        workspace: Optional workspace identifier
        agent_id: Optional agent identifier
        extras: Additional provider-specific data
        _client: Synchronous client instance
        _aclient: Asynchronous client instance
        _collector: Observability collector instance
    """
    config: LlmConfig
    session_id: str = Field(default_factory=ulid.ulid)
    worspace: Optional[str]=None
    agent_id: Optional[str]=None
    extras: Optional[dict]=Field(default_factory=dict)
    _client: Any = None
    _aclient: Any = None
    _completion_args: Dict = {}
    _completion_fn: Any = None
    _acompletion_fn: Any = None
    _normalize_fn: Any = None
    _tokenizer_fn: Any = None
    _is_reasoner: bool = False
    _usage :Optional[UsageInfo]=None
    _collector: Optional[LlmOperationCollector] = None

    @classmethod
    def from_config(cls, config: LlmConfig) -> "LlmBaseProvider":
        """Create provider instance from configuration.
        
        Args:
            config: LLM configuration to initialize the provider
            
        Returns:
            LlmBaseProvider: Initialized provider instance
            
        Example:
            >>> config = LlmConfig(provider="openai", api_key="...", model="gpt-4")
            >>> provider = LlmBaseProvider.from_config(config)
        """
        return cls(
            config=config
        )
    
    @property
    def client(self):
        """Get the synchronous client instance.
        
        Returns:
            The configured synchronous client
        """
        return self._client
    
    @client.setter
    def client(self, client: Any):
        """Set the synchronous client instance.
        
        Args:
            client: Client instance to set
        """
        self._client = client

    @property
    def aclient(self):
        """Get the asynchronous client instance.
        
        Returns:
            The configured asynchronous client
        """
        return self._aclient
    
    @client.setter
    def aclient(self, aclient: Any):
        """Set the asynchronous client instance.
        
        Args:
            aclient: Async client instance to set
        """
        self._aclient = aclient

    def validate_config(self, exception :Exception):
        """Validate provider configuration against available models.
        
        Args:
            exception: Exception type to raise if validation fails
            
        Raises:
            ModelError: If configured model is not available
            AuthenticationError: If provider authentication fails
        """
        try:
            if self.config.model in CUSTOM_MODELS:
                return
            models = self.client.models.list()
            models = [model.id for model in models.data]
            if self.config.model not in models:
                if self.config.model.endswith("-latest"):
                    model_id = "-".join(self.config.model.split("-")[:-1])
                    models_id = ["-".join(model.split("-")[:-1]) for model in models]
                    if model_id in models_id:
                        return
                elif f"models/{self.config.model}" in models:
                    return
                raise ModelError.from_model(self.config.model, self.config.provider, models)
        except exception as e:
            raise AuthenticationError(
                provider=self.config.provider,
                message=str(e)
            )

    @property
    def completion_args(self) -> Dict:
        """Get additional completion arguments.
        
        Returns:
            Dictionary of completion arguments
        """
        return self._completion_args
    
    @completion_args.setter
    def completion_args(self, args: Dict):
        """Set additional completion arguments.
        
        Args:
            args: Dictionary of completion arguments to set
        """
        self._completion_args = args

    @property
    def completion_fn(self) -> Any:
        """Get the synchronous completion function.
        
        Returns:
            The configured completion function
        """
        return self._completion_fn
    
    @completion_fn.setter
    def completion_fn(self, completion_fn: Any):
        """Set the synchronous completion function.
        
        Args:
            completion_fn: Completion function to set
        """
        self._completion_fn = completion_fn

    @property
    def acompletion_fn(self) -> Any:
        """Get the asynchronous completion function.
        
        Returns:
            The configured async completion function
        """
        return self._acompletion_fn
    
    @acompletion_fn.setter
    def acompletion_fn(self, acompletion_fn: Any):
        """Set the asynchronous completion function.
        
        Args:
            acompletion_fn: Async completion function to set
        """
        self._acompletion_fn = acompletion_fn

    @property
    def normalize_fn(self) -> Any:
        """Get the response normalization function.
        
        Returns:
            The configured normalization function
        """
        return self._normalize_fn
    
    @normalize_fn.setter
    def normalize_fn(self, normalize_fn: Any):
        """Set the response normalization function.
        
        Args:
            normalize_fn: Normalization function to set
        """
        self._normalize_fn = normalize_fn

    @property
    def tokenizer_fn(self) -> Any:
        """Get the tokenizer function.
        
        Returns:
            The configured tokenizer function
        """
        return self._tokenizer_fn
    
    @tokenizer_fn.setter
    def tokenizer_fn(self, tokenizer_fn: Any):
        """Set the tokenizer function.
        
        Args:
            tokenizer_fn: Tokenizer function to set
        """
        self._tokenizer_fn = tokenizer_fn

    @property
    def usage(self) -> UsageInfo:
        """Get usage information tracker.
        
        Returns:
            UsageInfo instance tracking token usage and costs
        """
        if self._usage is None:
            self._usage = UsageInfo.from_pricing_config(self.config.pricing)
        return self._usage
    
    @usage.setter
    def usage(self, usage :UsageInfo):
        """Set usage information tracker.
        
        Args:
            usage: UsageInfo instance to set
        """
        self._usage = usage
    
    @property
    def collector(self) -> Optional[LlmOperationCollector]:
        """Get the operation collector instance.
        
        Returns:
            LlmOperationCollector instance if configured, None otherwise
        """
        if self._collector is None:
            self._collector = LlmOperationCollector.fom_observable_storage_path()
        return self._collector
    
    @collector.setter
    def collector(self, collector: LlmOperationCollector):
        """Set the operation collector instance.
        
        Args:
            collector: LlmOperationCollector instance to set
        """
        self._collector = collector
        
    def disable_collection(self):
        """Disable data collection for this provider."""
        if self._collector:
            self._collector.is_enabled = False
    
    @staticmethod
    def get_default_tokenizer(model_name: str) -> str:
        """Get default tokenizer name for a model.
        
        Args:
            model_name: Name of the model to get tokenizer for
            
        Returns:
            str: Tokenizer name (falls back to 'gpt-4o' if unknown)
        """
        try:
            tiktoken.encoding_name_for_model(model_name)
            return model_name
        except KeyError:
            return "gpt-4o"

    @staticmethod
    def _message_content(prompt: Union[List[str], str], img_b64_str: Optional[List[str]] = None) -> Union[str, List[Dict]]:
        """Format message content for API requests.
        
        Args:
            prompt: Input prompt(s) to format
            img_b64_str: Optional list of base64 encoded images
            
        Returns:
            Union[str, List[Dict]]: Formatted message content as string or list of content parts
        """
        if isinstance(prompt, str):
            prompt = [prompt]

        if img_b64_str is None:
            message_content = "\n".join(prompt)
        else:
            message_content = [
                {
                    "type": "text",
                    "text": _prompt
                } for _prompt in prompt
            ]
            for img in img_b64_str:
                message_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}"},
                    }
                )
        return message_content
    
    @staticmethod
    def async_partial(func, *args, **kwargs):
        """Create async partial function with bound arguments.
        
        Args:
            func: Async function to partialize
            *args: Positional arguments to bind
            **kwargs: Keyword arguments to bind
            
        Returns:
            Callable: Async function with bound arguments
            
        Example:
            >>> async def test(a, b): return a + b
            >>> partial = async_partial(test, 1)
            >>> await partial(2)  # Returns 3
        """
        @wraps(func)
        async def wrapped(*inner_args, **inner_kwargs):
            return await func(*args, *inner_args, **kwargs, **inner_kwargs)
        return wrapped
    
    def use_as_reasoner(self, 
                        session_id :Optional[str]=None,
                        workspace :Optional[str]=None,
                        stop_thinking_token: str = REASONING_STOP_TOKEN):
        """Configure provider as a reasoning assistant.
        
        Args:
            session_id: Optional session identifier to set
            workspace: Optional workspace identifier to set
            stop_thinking_token: Token to stop reasoning output
            
        Example:
            >>> provider.use_as_reasoner(
            ...     session_id="123",
            ...     stop_thinking_token="[STOP_REASONING]"
            ... )
        """
        if self.session_id:
            self.session_id = session_id
        self.worspace = workspace
        self.completion_fn = partial(self.completion_fn, stop=stop_thinking_token)
        self.acompletion_fn = self.async_partial(self.acompletion_fn, stop=stop_thinking_token)
        self._is_reasoner = True

    def _message_body(self, prompt: Union[List[str], str], role: Literal["user", "system", "assistant"] = "user", img_b64_str: Optional[List[str]] = None, _last: Optional[bool] = False) -> Dict:
        """Create message body for API requests.
        
        Args:
            prompt: Input prompt(s) to include
            role: Message role (user/system/assistant)
            img_b64_str: Optional base64 encoded images
            _last: Whether this is the last message
            
        Returns:
            Dict: Formatted message body
        """
        message_body = {
            "role": role,
            "content": self._message_content(prompt, img_b64_str)
        }
        return message_body

    @staticmethod
    def _validte_message_dict(message_dict: Dict[str, str]) -> bool:
        """Validate message dictionary structure.
        
        Args:
            message_dict: Message dictionary to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            AssertionError: If message structure is invalid
        """
        assert message_dict.get("role") in ["user", "system", "assistant"], f"{message_dict} 'role' attribute must be one of ['user', 'system', 'assistant']"
        assert message_dict.get("content") is not None, f"{message_dict} 'content' attribute is missing"
        return True

    def _map_multiple_prompts(self, prompt: Union[List[str], List[Dict[str, str]]]) -> List[str]:
        """Map multiple prompts to message sequence with alternating roles.
        
        Args:
            prompt: List of prompts or message dictionaries
            
        Returns:
            List[str]: Sequence of formatted messages with alternating roles
        """
        next_role_maps = {
            "assistant": "user",
            "user": "assistant"
        }
        role = "user"
        prompt_messages = []
        for _prompt in prompt[::-1]:
            if isinstance(_prompt, str):
                _prompt = self._message_body(_prompt, role=role)
            
            elif isinstance(_prompt, dict):
                self._validte_message_dict(_prompt)
                role = _prompt.get("role")
            
            role = next_role_maps.get(role)
            prompt_messages.append(_prompt)
        
        return prompt_messages[::-1]
    
    def _handle_system_prompt(self,
        messages :list,
        system_prompt: Optional[Union[List[str], str]] = None):
        """Handle system prompt for API requests.
        
        Args:
            messages: List of messages to append to
            system_prompt: System prompt content to add
        """
        if system_prompt is not None:
            messages.append(self._message_body(system_prompt, role="system"))

    def _handle_special_sys_prompt_anthropic(self, args :Dict, system_prompt: Optional[Union[List[str], str]] = None):
        """placeholder to be overwritten by the anthropic provider"""
        pass

    def completion_args_template(self,
        prompt: Union[str, List[str], List[Dict[str, str]]],
        system_prompt: Optional[Union[List[str], str]] = None,
        prefix_prompt: Optional[Union[List[str], str]] = None,
        img_b64_str: Optional[Union[str, List[str]]] = None,
        stream: bool = False) -> Dict:
        """Create completion arguments template for API requests.
        
        Args:
            prompt: Input prompt(s)
            system_prompt: Optional system prompt
            prefix_prompt: Optional prefix prompt
            img_b64_str: Optional base64 encoded images
            stream: Whether to stream response
            
        Returns:
            Dict: Prepared completion arguments
        """
        if img_b64_str and isinstance(img_b64_str, str):
            img_b64_str = [img_b64_str]
        if isinstance(prompt, str):
            prompt = [prompt]

        messages = []
        self._handle_system_prompt(messages, system_prompt)

        messages.extend(self._map_multiple_prompts(prompt))

        if prefix_prompt is not None:
            messages.append(self._message_body(prefix_prompt, role="assistant", _last=True))
        
        args = dict(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            messages=messages,
            stream=stream
        )
        
        if self.completion_args:
            if not stream:
                self.completion_args.pop("stream_options", None)
            args.update(self.completion_args)

        self._handle_special_sys_prompt_anthropic(args, system_prompt)
        
        args = {arg: value for arg, value in args.items() if value is not None}
        
        return args

    def _prepare_completion_args(self,
        prompt: Union[str, List[str], List[Dict[str, str]]], 
        system_prompt: Optional[Union[List[str], str]] = None,
        prefix_prompt: Optional[Union[List[str], str]] = None,
        img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]] = None,
        stream: bool = True) -> Dict:
        """Prepare completion arguments including image processing.
        
        Args:
            prompt: Input prompt(s)
            system_prompt: Optional system prompt
            prefix_prompt: Optional prefix prompt
            img_path: Optional image path(s)
            stream: Whether to stream response
            
        Returns:
            Dict: Prepared completion arguments
        """
        if img_path and not isinstance(img_path, list):
            img_path = [img_path]
        
        img_b64_str = [
            image_to_base64(img)
            for img in img_path
        ] if img_path else None

        completion_args = self.completion_args_template(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_b64_str=img_b64_str,
            stream=stream
        )
        return completion_args
    
    @staticmethod
    def _handle_reasoning_steps(chunk_message, message, _skip)->bool:
        """Handle reasoning steps in streamed responses.
        
        Args:
            chunk_message: Current message chunk
            message: Accumulated message
            _skip: Whether to skip current chunk
            
        Returns:
            bool: Updated skip state
        """
        if chunk_message == REASONING_START_TOKEN:
            _skip = True
        message.append(chunk_message) if not _skip else ... 
        if chunk_message == REASONING_STOP_TOKEN:
            _skip = False        
        return _skip

    @classmethod
    def _handle_stream_messages(cls, _chunk, message, _skip=False)->bool:
        """Handle streamed messages from synchronous completions.
        
        Args:
            _chunk: Raw message chunk
            message: Accumulated message
            _skip: Whether to skip current chunk
            
        Returns:
            bool: Updated skip state
        """
        chunk_message = _chunk[0].delta.content or ""
        default_stream_handler(chunk_message)
        return cls._handle_reasoning_steps(chunk_message, message, _skip)
    
    @classmethod
    async def _handle_astream_messages(cls, _chunk, logger_fn, message, _skip=False)->bool:
        """Handle streamed messages from asynchronous completions.
        
        Args:
            _chunk: Raw message chunk
            logger_fn: Async logging function
            message: Accumulated message
            _skip: Whether to skip current chunk
            
        Returns:
            bool: Updated skip state
        """
        chunk_message = _chunk[0].delta.content or  ""
        await logger_fn(chunk_message)
        return cls._handle_reasoning_steps(chunk_message, message, _skip)

    def _stream(self, stream, prefix_prompt: Optional[Union[str, List[str]]] = None) -> str:
        """Handle streaming response from synchronous completion.
        
        Args:
            stream: Response stream
            prefix_prompt: Optional prefix prompt
            
        Returns:
            str: Accumulated response
        """
        message = [] 
        _skip = False
        completeion_id = ulid.ulid()
        for chunk in stream:
            _chunk = self.normalize_fn(chunk, completeion_id)
            if _chunk:
                _skip = self._handle_stream_messages(_chunk, message, _skip)

        if self._is_reasoner:
            default_stream_handler(REASONING_STOP_TOKEN)
        else:
            default_stream_handler(STREAM_END_TOKEN)

        response = "".join(message)
        return response
    
    async def _astream(self, stream, logger_fn, prefix_prompt: Optional[Union[str, List[str]]] = None) -> str:
        """Handle streaming response from asynchronous completion.
        
        Args:
            stream: Async response stream
            logger_fn: Async logging function
            prefix_prompt: Optional prefix prompt
            
        Returns:
            str: Accumulated response
        """
        message = []
        _skip = False        
        completeion_id = ulid.ulid()
        await logger_fn(STREAM_START_TOKEN) if not prefix_prompt else ...
        async for chunk in stream:
            _chunk = self.normalize_fn(chunk, completeion_id)
            if _chunk:
                _skip = await self._handle_astream_messages(_chunk, logger_fn, message, _skip)
        
        if self._is_reasoner:
            await logger_fn(REASONING_STOP_TOKEN)
        else:
            await logger_fn(STREAM_END_TOKEN)
        response = "".join(message)
        return response
    
    @staticmethod
    def model_to_str(model: Union[BaseModel, RootModel]) -> str:
        """Convert model to JSON string representation."""
        return f"```json\n{model.model_dump_json(indent=4)}\n```"
    
    @staticmethod
    def extract_json(output: str) -> Dict:
        try:
            return json.loads(parse_content(output))
        except json.JSONDecodeError:
            return output

    def complete(
        self,
        prompt: Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel], 
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]] = None,
        json_output: bool = False,
        stream: bool = True,
        agent_id: Optional[str]=None,
        action_id :Optional[str]=None) -> Union[str, Dict]:
        """
        Complete a prompt using the LLM provider.
            
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
        """
        
        if isinstance(prompt, Union[BaseModel, RootModel]):
            prompt = self.model_to_str(prompt)
        
        # Start tracking operation time
        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        cost = 0
        
        completion_args = self._prepare_completion_args(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_path=img_path,
            stream=stream
        )
        
        output = None  
        error_message = None
        try:
            output = self.completion_fn(**completion_args)
            
            if stream:
                output = self._stream(output, prefix_prompt)
            if self.usage:
                if self.usage.latest_completion:
                    _logger.logger.info(str(self.usage.latest_completion))
                    input_tokens = self.usage.latest_completion.prompt_tokens
                    output_tokens = self.usage.latest_completion.response_tokens
                    cost = self.usage.latest_completion.cost
                _logger.logger.info(str(self.usage))
            
            output = output if not json_output else self.extract_json(output)

        except Exception as e:
            error_message = str(e)
            output = None 
            raise e
        
        finally:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            if self.collector:
                self.collector.record_completion(
                    provider=self.config.provider,
                    operation_type="completion",
                    completion_args=completion_args,
                    response=output,
                    session_id=self.session_id,
                    workspace=self.worspace,
                    agent_id=agent_id or self.agent_id,
                    action_id=action_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    latency_ms=latency_ms,
                    error_message=error_message,
                    extras=self.extras
                )
            
        return output

    async def acomplete(
        self,
        prompt: Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel],
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]] = None,
        json_output: bool = False,
        stream: bool = True,
        stream_handler: Optional[Callable[[str], None]] = default_stream_handler,
        agent_id: Optional[str]=None,
        action_id :Optional[str]=None
        ) -> Union[str, Dict]:
        """
        Async version of complete() to generate completions.
        
        Args:
            prompt: Input prompt (can be str, list, dict, BaseModel or RootModel)
            system_prompt: Optional system prompt override
            prefix_prompt: Additional context to prepend
            img_path: Optional image path(s) for multimodal input
            json_output: Whether to parse output as JSON
            stream: Whether to stream the response
            stream_handler: default_stream_handler
            agent_id: Optional agent identifier
            action_id: Optional action identifier
            
        Returns:
            The completion result as either a string or dictionary (if json_output=True)
        """
        
        if isinstance(prompt, Union[BaseModel, RootModel]):
            prompt = self.model_to_str(prompt)

        stream_handler = stream_handler or default_stream_handler
        
        # Start tracking operation time
        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        cost = 0
        
        completion_args = self._prepare_completion_args(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_path=img_path,
            stream=stream
        )
        
        output = None 
        error_message = None
        try:
            output = await self.acompletion_fn(**completion_args)
            
            if stream:
                output = await self._astream(output, stream_handler, prefix_prompt)
            if self.usage:
                if self.usage.latest_completion:
                    _logger.logger.info(str(self.usage.latest_completion))
                    input_tokens = self.usage.latest_completion.prompt_tokens
                    output_tokens = self.usage.latest_completion.response_tokens
                    cost = self.usage.latest_completion.cost
                _logger.logger.info(str(self.usage))
            
            output = output if not json_output else self.extract_json(output)

        except Exception as e:
            error_message = str(e)
            output = None 
            raise e
        
        finally:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            if self.collector:
                await self.collector.arecord_completion(
                    provider=self.config.provider,
                    operation_type="acompletion",
                    completion_args=completion_args,
                    response=output,
                    session_id=self.session_id,
                    workspace=self.worspace,
                    agent_id=agent_id or self.agent_id,
                    action_id=action_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    latency_ms=latency_ms,
                    error_message=error_message,
                    extras=self.extras
                )
            
        return output