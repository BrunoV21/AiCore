"""
Base provider class for LLM implementations with common functionality.
This module defines the base class for all LLM providers in the system, providing
common interfaces and utilities for synchronous and asynchronous operations.
"""

from aicore.llm.config import LlmConfig
from aicore.llm.mcp.client import MCPClient
from aicore.llm.mcp.models import ToolCallSchema, ToolCalls, ToolSchema
from aicore.logger import _logger, default_stream_handler
from aicore.const import REASONING_START_TOKEN, REASONING_STOP_TOKEN, STREAM_START_TOKEN, STREAM_END_TOKEN, CUSTOM_MODELS, TOOL_CALL_END_TOKEN, TOOL_CALL_START_TOKEN
from aicore.llm.utils import parse_content, image_to_base64
from aicore.llm.usage import UsageInfo
from aicore.models import AuthenticationError, ModelError
from aicore.models_metadata import METADATA
from aicore.observability.collector import LlmOperationCollector
from typing import Any, Dict, Optional, Literal, List, Tuple, Union, Callable
from pydantic import BaseModel, RootModel, Field
from functools import partial, wraps
from json_repair import repair_json
from pathlib import Path
import tiktoken
import asyncio
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
    tools: Optional[List[ToolSchema]]=None
    _client: Any = None
    _aclient: Any = None
    _completion_args: Dict = {}
    _completion_fn: Any = None
    _acompletion_fn: Any = None
    _normalize_fn: Any = None
    _tokenizer_fn: Any = None
    _is_reasoner: bool = False
    _auth_exception: Exception = Exception
    _usage :Optional[UsageInfo]=None
    _collector: Optional[LlmOperationCollector] = None
    _mcp: Optional[MCPClient] = None
    _n_sucessive_tool_calls :int=0

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
    
    @aclient.setter
    def aclient(self, aclient: Any):
        """Set the asynchronous client instance.
        
        Args:
            aclient: Async client instance to set
        """
        self._aclient = aclient

    def validate_config(self, force_check_against_provider :bool=False):
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
            
            if not force_check_against_provider and self.config.provider_model in METADATA:
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
        except self._auth_exception as e:
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

    @property
    def mcp(self)->MCPClient:
        if self.config.mcp_config_path and self._mcp is None:
            self._mcp = MCPClient.from_config(self.config.mcp_config_path)
        elif self._mcp is None:            
            self._mcp = MCPClient()
        return self._mcp
    
    @mcp.setter
    def mcp(self, client :MCPClient):
        self._mcp = client

    @staticmethod
    def _to_provider_tool_schema(tool_schema: ToolSchema)->Dict[str, Any]:
        raise NotImplementedError("the selected model-provider does not support tool calling")
    
    @staticmethod
    def _to_provider_tool_call_schema(toolCallSchema :ToolCallSchema)->ToolCallSchema:        
        raise NotImplementedError("the selected model-provider does not support tool calling")

    def _tool_call_message(self, **kwargs)->Dict[str, str]:        
        raise NotImplementedError("the selected model-provider does not support tool calling")

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
        assert message_dict.get("role") in ["user", "system", "assistant", "tool"], f"{message_dict} 'role' attribute must be one of ['user', 'system', 'assistant', 'tool]"
        assert message_dict.get("content") is not None or message_dict.get("tool_calls") is not None, f"{message_dict} 'content' or 'tool_calls' attribute is missing"
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

            elif isinstance(_prompt, ToolCallSchema):
                _prompt = _prompt._raw
            
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

    def _handle_openai_response_only_models(self, args :Dict):
        """Placeholder to be overwritten by the openai provider"""
        pass

    @classmethod
    def _handle_tools(cls, tools  :List[ToolSchema])->Dict:
        if not tools:
            return None
        return [
            cls._to_provider_tool_schema(tool)
            for tool in tools
        ]

    def completion_args_template(self,
        prompt: Union[str, List[str], List[Dict[str, str]]],
        system_prompt: Optional[Union[List[str], str]] = None,
        prefix_prompt: Optional[Union[List[str], str]] = None,
        img_b64_str: Optional[Union[str, List[str]]] = None,
        tools: Optional[List[ToolSchema]]=None,
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
            tools=tools,
            tool_choice=self.config.tool_choice,
            stream=stream
        )
        
        if self.completion_args:
            if not stream:
                self.completion_args.pop("stream_options", None)
            args.update(self.completion_args)

        self._handle_openai_response_only_models(args)
        self._handle_special_sys_prompt_anthropic(args, system_prompt)
        
        args = {arg: value for arg, value in args.items() if value is not None}
        
        return args
    
    @staticmethod
    def _img_to_base64(img_path :Optional[Union[Union[str, Path, bytes], List[Union[str, Path, bytes]]]] = None):
        return [
            image_to_base64(img)
            for img in img_path
        ] if img_path else None

    def _prepare_completion_args(self,
        prompt: Union[str, List[str], List[Dict[str, str]]], 
        system_prompt: Optional[Union[List[str], str]] = None,
        prefix_prompt: Optional[Union[List[str], str]] = None,
        img_b64_str: Optional[List[str]] = None,
        tools: Optional[List[ToolSchema]]=None,
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

        completion_args = self.completion_args_template(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_b64_str=img_b64_str,
            tools=tools,
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
    def _is_tool_call(cls, _chunk)->bool:
        if _chunk and hasattr(cls._chunk_from_provider(_chunk).delta, "tool_calls") and cls._chunk_from_provider(_chunk).delta.tool_calls:
            return True
        return False

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
    
    @staticmethod
    def _chunk_from_provider(_chunk):
        return _chunk[0]
    
    @classmethod
    def _tool_chunk_from_provider(cls, _chunk):
        return cls._chunk_from_provider(_chunk).delta.tool_calls[0]
    
    @staticmethod
    def _fill_tool_schema(tool_chunk)->ToolCallSchema:
        tool_call = ToolCallSchema(
            id=tool_chunk.id,
            name=tool_chunk.function.name,
            arguments=tool_chunk.function.arguments
        )
        tool_call._raw = tool_chunk.function
        return tool_call
    
    @staticmethod
    def _tool_call_change_condition(tool_chunk)->bool:
        return tool_chunk.id is not None
    
    @staticmethod
    def _handle_tool_call_stream(tool_call :ToolCallSchema, tool_chunk)->ToolCallSchema:
        tool_call._raw.arguments += tool_chunk.function.arguments
        tool_call.arguments += tool_chunk.function.arguments
        return tool_call

    def _no_stream(self, response) -> Union[str, ToolCalls]:
        _chunk = self.normalize_fn(response)
        message = self._chunk_from_provider(_chunk).message
        if hasattr(message, "tool_calls") and message.tool_calls:
            return ToolCalls(root=[
                self._fill_tool_schema(tool_call) for tool_call in message.tool_calls
            ])
        else:
            return message.content

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
    
    async def _astream(self, stream, logger_fn, prefix_prompt: Optional[Union[str, List[str]]] = None) -> Union[str, ToolCalls]:
        """Handle streaming response from asynchronous completion.
        
        Args:
            stream: Async response stream
            logger_fn: Async logging function
            prefix_prompt: Optional prefix prompt
            
        Returns:
            str: Accumulated response
        """
        message :List[Union[str, ToolCallSchema]] = []
        _skip = False
        completeion_id = ulid.ulid()
        await logger_fn(STREAM_START_TOKEN) if not prefix_prompt else ...
        _calling_tool = False
        tool_calls = ToolCalls()
        async for chunk in stream:
            _chunk = self.normalize_fn(chunk, completeion_id)
            if _chunk:
                _skip = await self._handle_astream_messages(_chunk, logger_fn, message, _skip)

            if self._is_tool_call(_chunk):
                ### TODO recheck this line to ensure it covers multiple tool calling in stream mode
                tool_chunk = self._tool_chunk_from_provider(_chunk)
                if not _calling_tool:
                    _calling_tool = True
                    await logger_fn(TOOL_CALL_START_TOKEN)
                    tool_call = self._fill_tool_schema(tool_chunk)
                    continue

                if self._tool_call_change_condition(tool_chunk):
                    if message:
                        ### cover anthropic
                        tool_call._raw = "\n".join(message)
                    tool_calls.root.append(tool_call)
                    tool_call = self._fill_tool_schema(tool_chunk)
                    continue
                
                tool_call = self._handle_tool_call_stream(tool_call, tool_chunk)
        
        if _calling_tool:
            ### colect last call
            if message:
                ### cover anthropic
                tool_call._raw = "\n".join(message)
            tool_calls.root.append(tool_call)
            return tool_calls
        
        if self._is_reasoner:
            await logger_fn(REASONING_STOP_TOKEN)
        else:
            await logger_fn(STREAM_END_TOKEN)
        response = "".join(message)
        return response
    
    async def connect_to_mcp(self):
        if self.mcp is not None and self.config.tool_use is not False:
            if not self.mcp._is_connected or self.mcp._needs_update:
                await self.mcp.connect()
                tools = await self.mcp.servers.tools
                self.tools = self._handle_tools(tools)
                self.mcp._needs_update = False

    @property
    def _has_not_exceeded_tool_calls(self)->bool:
        return self.config.max_tool_calls_per_response is None  or self._n_sucessive_tool_calls < self.config.max_tool_calls_per_response
    
    async def _execute_tool_calls(self, output :list)->Tuple[list, bool]:
        """
        Execute multiple tool calls in parallel using asyncio.gather.
        
        Args:
            output: The output containing potential tool calls
            logger: Logger instance for logging execution information
        
        Returns:
            List of tool messages generated from tool calls
        """
        tools_messages = []
        call_tool = False
        
        for _output in output:
            if isinstance(_output, ToolCalls) and self._has_not_exceeded_tool_calls:
                call_tool = True
                tool_calls = _output.root
                
                # If there are multiple tool calls, execute them in parallel
                if len(tool_calls) > 1 and self.config.concurrent_tool_calls:
                    
                    tool_names = [tool_call.name for tool_call in tool_calls]
                    # Log the start of tool execution
                    _logger.logger.info(f"Executing {len(tool_calls)} tools: {tool_names}")
                    start_time = time.time()
                    
                    tool_coroutines = [
                        self.mcp.servers.call_tool(
                            tool_name=tool_call.name,
                            arguments=json.loads(repair_json(tool_call.arguments) or "{}"),
                            silent=True
                        )
                        for tool_call in tool_calls
                    ]
                    
                    # Execute all tool calls in parallel
                    tool_responses = await asyncio.gather(*tool_coroutines)
                    
                    # Process the responses
                    for tool_call, tool_call_response in zip(tool_calls, tool_responses):
                        tools_messages.extend([
                            self._to_provider_tool_call_schema(tool_call),
                            self._tool_call_message(toolCallSchema=tool_call, content=tool_call_response),
                        ])

                    execution_time = time.time() - start_time
                    _logger.logger.info(f"Finished executing {len(tool_calls)} tools in {execution_time:.2f} seconds")
                else:
                    # If there's only one tool call, execute it directly
                    for tool_call in tool_calls:
                        tool_call_response = await self.mcp.servers.call_tool(
                            tool_name=tool_call.name,
                            arguments=json.loads(repair_json(tool_call.arguments) or "{}"),
                        )
                        tools_messages.extend([
                            self._to_provider_tool_call_schema(tool_call),
                            self._tool_call_message(toolCallSchema=tool_call, content=tool_call_response)
                        ])
                    
            elif isinstance(_output, str):
                tools_messages.append(self._message_body(_output, role="assistant"))
        
        return tools_messages, call_tool

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
  
    @staticmethod
    def _get_message_records(completion_args :Dict[str, str], excluded_roles :Optional[List[Literal["user", "system", "assistant"]]]=None)->List[Dict[str, str]]:
        messages = completion_args.get("messages")
        records = [
            message for message in messages
            if not excluded_roles or message.get("role") not in excluded_roles
        ]
        return records

    def complete(
        self,
        prompt: Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel], 
        system_prompt: Optional[Union[str, List[str]]] = None,
        prefix_prompt: Optional[Union[str, List[str]]] = None,
        img_path: Optional[Union[Union[str, Path, bytes], List[Union[str, Path, bytes]]]] = None,
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
        img_b64_str = self._img_to_base64(img_path)
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
            img_b64_str=img_b64_str,
            stream=stream
        )
        
        output = None
        error_message = None
        try:
            output = self.completion_fn(**completion_args)
            
            if stream:
                output = self._stream(output, prefix_prompt)
            else:
                output = self._no_stream(output)

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
        as_message_records :bool=False,
        stream_handler: Optional[Callable[[str], None]] = default_stream_handler,
        agent_id: Optional[str]=None,
        action_id :Optional[str]=None
        ) -> Union[str, Dict, List[Union[str, Dict[str, str]]]]:
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
        img_b64_str = self._img_to_base64(img_path)
        if isinstance(prompt, Union[BaseModel, RootModel]):
            prompt = self.model_to_str(prompt)
        elif isinstance(prompt, str):            
            prompt = [self._message_body([prompt], role="user", img_b64_str=img_b64_str)]
        
        stream_handler = stream_handler or default_stream_handler
        
        # Start tracking operation time
        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        cost = 0

        await self.connect_to_mcp()
        
        completion_args = self._prepare_completion_args(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_b64_str=img_b64_str,
            tools=self.tools if self._has_not_exceeded_tool_calls else None,
            stream=stream
        )
        output = None 
        call_tool = False
        error_message = None
        try:
            output = await self.acompletion_fn(**completion_args)
            
            if stream:
                output = await self._astream(output, stream_handler, prefix_prompt)
            else:
                output = self._no_stream(output)
            
            if self.usage:
                if self.usage.latest_completion:
                    _logger.logger.info(str(self.usage.latest_completion))
                    input_tokens = self.usage.latest_completion.prompt_tokens
                    output_tokens = self.usage.latest_completion.response_tokens
                    cost = self.usage.latest_completion.cost
                _logger.logger.info(str(self.usage))
            
            ### handle scenarios of text + toolcalssblock i.e anthropic
            _is_not_list = False
            if not isinstance(output, list):
                _is_not_list = True
                output = [output]
            
            tools_messages, call_tool = await self._execute_tool_calls(output)

            if call_tool:
                output = [
                    _.model_dump() if isinstance(_, ToolCalls) else _ for _ in output
                ]
                if stream:
                    await stream_handler(TOOL_CALL_END_TOKEN)
                
                messages = completion_args.get("messages")
                messages = [_ for _ in messages]
                messages.extend(tools_messages)
                self._n_sucessive_tool_calls += 1

                if self.collector:
                    end_time = time.time()
                    latency_ms = (end_time - start_time) * 1000
                    await self.collector.arecord_completion(
                        provider=self.config.provider,
                        operation_type="acompletion.tool_call",
                        completion_args=completion_args,
                        response=output.model_dump_json(indent=4) if isinstance(output, ToolCalls) else output,
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

                return await self.acomplete(
                    prompt=messages,
                    system_prompt=system_prompt,
                    prefix_prompt=prefix_prompt,
                    img_path=img_path,
                    json_output=json_output,
                    stream=stream,
                    as_message_records=as_message_records,
                    stream_handler=stream_handler,
                    agent_id=agent_id,
                    action_id=action_id
                )
            
            self._n_sucessive_tool_calls = 0
            if _is_not_list:
                output = output[-1]
            
            output = output if not json_output else self.extract_json(output)

        except Exception as e:
            error_message = str(e)
            output = None 
            raise e
        
        finally:
            if not call_tool:
                if self.collector:
                    end_time = time.time()
                    latency_ms = (end_time - start_time) * 1000
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
        
        if as_message_records:
            records = self._get_message_records(completion_args, excluded_roles=["system"])
            records.append(output)
            output = records
            
        return output