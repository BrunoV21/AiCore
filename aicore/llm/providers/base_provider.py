
from aicore.llm.config import LlmConfig
from aicore.logger import _logger
from aicore.const import REASONING_START_TOKEN, REASONING_STOP_TOKEN, STREAM_START_TOKEN, STREAM_END_TOKEN
from aicore.llm.utils import parse_content, image_to_base64, default_stream_handler
from aicore.llm.usage import UsageInfo
from aicore.observability.collector import LlmOperationCollector
from aicore.observability.storage import OperationStorage
from typing import Any, Dict, Optional, Literal, List, Union, Callable
from pydantic import BaseModel, RootModel
from functools import partial, wraps
from pathlib import Path
import tiktoken
import json
import time
from copy import deepcopy

class LlmBaseProvider(BaseModel):
    config: LlmConfig
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
        return cls(
            config=config
        )
    
    @property
    def client(self):
        return self._client
    
    @client.setter
    def client(self, client: Any):
        self._client = client

    @property
    def aclient(self):
        return self._aclient
    
    @client.setter
    def aclient(self, aclient: Any):
        self._aclient = aclient

    @property
    def completion_args(self) -> Dict:
        return self._completion_args
    
    @completion_args.setter
    def completion_args(self, args: Dict):
        self._completion_args = args

    @property
    def completion_fn(self) -> Any:
        return self._completion_fn
    
    @completion_fn.setter
    def completion_fn(self, completion_fn: Any):
        self._completion_fn = completion_fn

    @property
    def acompletion_fn(self) -> Any:
        return self._acompletion_fn
    
    @acompletion_fn.setter
    def acompletion_fn(self, acompletion_fn: Any):
        self._acompletion_fn = acompletion_fn

    @property
    def normalize_fn(self) -> Any:
        return self._normalize_fn
    
    @normalize_fn.setter
    def normalize_fn(self, normalize_fn: Any):
        self._normalize_fn = normalize_fn

    @property
    def tokenizer_fn(self) -> Any:
        return self._tokenizer_fn
    
    @tokenizer_fn.setter
    def tokenizer_fn(self, tokenizer_fn: Any):
        self._tokenizer_fn = tokenizer_fn

    @property
    def usage(self) -> UsageInfo:
        if self._usage is None:
            self._usage = UsageInfo.from_pricing_config(self.config.pricing)
        return self._usage
    
    @usage.setter
    def usage(self, usage :UsageInfo):
        self._usage = usage
    
    @property
    def collector(self) -> Optional[LlmOperationCollector]:
        """Get the operation collector instance."""
        if self._collector is None:
            # Initialize collector with storage
            storage = OperationStorage()
            self._collector = LlmOperationCollector(
                storage_callback=storage.store_record
            )
        return self._collector
    
    @collector.setter
    def collector(self, collector: LlmOperationCollector):
        """Set the operation collector instance."""
        self._collector = collector
        
    def disable_collection(self):
        """Disable data collection for this provider."""
        if self._collector:
            self._collector.is_enabled = False
    
    @staticmethod
    def get_default_tokenizer(model_name: str) -> str:
        try:
            tiktoken.encoding_name_for_model(model_name)
            return model_name
        except KeyError:
            return "gpt-4o"

    @staticmethod
    def _message_content(prompt: Union[List[str], str], img_b64_str: Optional[List[str]] = None) -> Union[str, List[Dict]]:
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
        @wraps(func)
        async def wrapped(*inner_args, **inner_kwargs):
            return await func(*args, *inner_args, **kwargs, **inner_kwargs)
        return wrapped
    
    def use_as_reasoner(self, stop_thinking_token: str = REASONING_STOP_TOKEN):
        """
        pass stop token to completion fn
        """
        self.completion_fn = partial(self.completion_fn, stop=stop_thinking_token)
        self.acompletion_fn = self.async_partial(self.acompletion_fn, stop=stop_thinking_token)
        self._is_reasoner = True

    def _message_body(self, prompt: Union[List[str], str], role: Literal["user", "system", "assistant"] = "user", img_b64_str: Optional[List[str]] = None, _last: Optional[bool] = False) -> Dict:
        message_body = {
            "role": role,
            "content": self._message_content(prompt, img_b64_str)
        }
        if role == "assistant" and self.config.provider == "mistral" and _last:
            message_body["prefix"] = True
        return message_body

    @staticmethod
    def _validte_message_dict(message_dict: Dict[str, str]) -> bool:
        assert message_dict.get("role") in ["user", "system", "assistant"], f"{message_dict} 'role' attribute must be one of ['user', 'system', 'assistant']"
        assert message_dict.get("content") is not None, f"{message_dict} 'content' attribute is missing"
        return True

    def _map_multiple_prompts(self, prompt: Union[List[str], List[Dict[str, str]]]) -> List[str]:
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

    def completion_args_template(self,
                                prompt: Union[str, List[str], List[Dict[str, str]]],
                                system_prompt: Optional[Union[List[str], str]] = None,
                                prefix_prompt: Optional[Union[List[str], str]] = None,
                                img_b64_str: Optional[Union[str, List[str]]] = None,
                                stream: bool = False) -> Dict:
        
        if img_b64_str and isinstance(img_b64_str, str):
            img_b64_str = [img_b64_str]
        if isinstance(prompt, str):
            prompt = [prompt]

        messages = []
        if system_prompt is not None:
            messages.append(self._message_body(system_prompt, role="system"))

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
        
        return args

    def _prepare_completion_args(self,
                                prompt: Union[str, List[str], List[Dict[str, str]]], 
                                system_prompt: Optional[Union[List[str], str]] = None,
                                prefix_prompt: Optional[Union[List[str], str]] = None,
                                img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]] = None,
                                stream: bool = True) -> Dict:
        if img_path and not isinstance(img_path, list):
            img_path = [img_path]

        # Store original request args for observability
        request_args = {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "img_path": str(img_path) if img_path else None,
            "stream": stream
        }
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
        
        # Add completion args to request_args for tracking
        tracked_args = deepcopy(request_args)
        # Remove potentially large message contents
        if "messages" in completion_args:
            tracked_args["message_count"] = len(completion_args["messages"])
        tracked_args["model"] = completion_args.get("model", self.config.model)
        tracked_args["temperature"] = completion_args.get("temperature", self.config.temperature)
        tracked_args["max_tokens"] = completion_args.get("max_tokens", self.config.max_tokens)
        
        # Store the prepared args in the completion_args for access in complete methods
        completion_args["_tracked_args"] = tracked_args

        return completion_args
    

    def _stream(self, stream, prefix_prompt: Optional[Union[str, List[str]]] = None) -> str:
        message = []

        for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                default_stream_handler(chunk_message)
                message.append(chunk_message)
        
        if self._is_reasoner:
            default_stream_handler(REASONING_STOP_TOKEN)
        response = "".join(message)
        return response
    
    async def _astream(self, stream, logger_fn, prefix_prompt: Optional[Union[str, List[str]]] = None) -> str:
        message = []
    
        await logger_fn(STREAM_START_TOKEN) if not prefix_prompt else ...
        async for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            # # Try to extract token usage for tracking
            # if hasattr(chunk, "usage") and chunk.usage:
            #     stream._tracked_token_usage = chunk.usage
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                await logger_fn(chunk_message)
                message.append(chunk_message)
        
        if self._is_reasoner:
            await logger_fn(REASONING_STOP_TOKEN)
        else:
            await logger_fn(STREAM_END_TOKEN)
        response = "".join(message)
        return response
    
    @staticmethod
    def model_to_str(model: Union[BaseModel, RootModel]) -> str:
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
                stream: bool = True) -> Union[str, Dict]:
        
        if isinstance(prompt, Union[BaseModel, RootModel]):
            prompt = self.model_to_str(prompt)
        
        # Start tracking operation time
        start_time = time.time()
        
        completion_args = self._prepare_completion_args(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_path=img_path,
            stream=stream
        )
        
        # Extract tracked args before removing them from completion_args
        tracked_args = completion_args.pop("_tracked_args", {})
        
        success = True
        error_message = None
        output = None
        
        try:
            output = self.completion_fn(**completion_args)
            
            if stream:
                output = self._stream(output, prefix_prompt)
            _logger.logger.info(str(self.usage.latest_completion)) if self.usage.latest_completion else ...
            _logger.logger.info(str(self.usage)) if self.usage else ...
            
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            # Calculate operation time
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            # Attempt to extract token information
            input_tokens = None
            output_tokens = None
            if hasattr(output, "usage"):
                input_tokens = getattr(output.usage, "prompt_tokens", None)
                output_tokens = getattr(output.usage, "completion_tokens", None)
            
            # # Record the operation
            # if self.collector:
            #     self.collector.record_operation(
            #         provider=self.config.provider,
            #         model=self.config.model,
            #         operation_type="completion",
            #         request_args=tracked_args,
            #         response=str(output)[:1000] if success else None,  # Limit response size
            #         input_tokens=input_tokens,
            #         output_tokens=output_tokens,
            #         latency_ms=latency_ms,
            #         success=success,
            #         error_message=error_message
            #     )

        if not success:
            return None

        return output if not json_output else self.extract_json(output)

    async def acomplete(
                        self,
                        prompt: Union[str, List[str], List[Dict[str, str]], BaseModel, RootModel],
                        system_prompt: Optional[Union[str, List[str]]] = None,
                        prefix_prompt: Optional[Union[str, List[str]]] = None,
                        img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]] = None,
                        json_output: bool = False,
                        stream: bool = True,
                        stream_handler: Optional[Callable[[str], None]] = default_stream_handler) -> Union[str, Dict]:
        
        if isinstance(prompt, Union[BaseModel, RootModel]):
            prompt = self.model_to_str(prompt)
        
        # Start tracking operation time
        start_time = time.time()
        
        completion_args = self._prepare_completion_args(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_path=img_path,
            stream=stream
        )
        
        # Extract tracked args before removing them from completion_args
        tracked_args = completion_args.pop("_tracked_args", {})
        
        success = True
        error_message = None
        output = None
        tracked_token_usage = None
        
        try:
            output = await self.acompletion_fn(**completion_args)
            
            if stream:
                output = await self._astream(output, stream_handler, prefix_prompt)
            _logger.logger.info(str(self.usage.latest_completion)) if self.usage.latest_completion else ...
            _logger.logger.info(str(self.usage)) if self.usage else ...
            
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            # Calculate operation time
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            # Attempt to extract token information
            input_tokens = None
            output_tokens = None
            if hasattr(output, "usage"):
                input_tokens = getattr(output.usage, "prompt_tokens", None)
                output_tokens = getattr(output.usage, "completion_tokens", None)
            elif tracked_token_usage:
                input_tokens = getattr(tracked_token_usage, "prompt_tokens", None)
                output_tokens = getattr(tracked_token_usage, "completion_tokens", None)
            
            # Record the operation
            # if self.collector:
            #     self.collector.record_operation(
            #         provider=self.config.provider,
            #         model=self.config.model,
            #         operation_type="acompletion",
            #         request_args=tracked_args,
            #         response=str(output)[:1000] if success else None,  # Limit response size
            #         input_tokens=input_tokens,
            #         output_tokens=output_tokens,
            #         latency_ms=latency_ms,
            #         success=success,
            #         error_message=error_message
            #     )
        
        if not success:
            return None
            
        return output if not json_output else self.extract_json(output)