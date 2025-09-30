from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.llm.mcp.models import ToolCallSchema, ToolCalls, ToolSchema
from aicore.logger import default_stream_handler
from aicore.const import OPENAI_NO_TEMPERATURE_MODELS, OPENAI_RESPONSE_API_MODELS
from pydantic import model_validator
from openai import OpenAI, AsyncOpenAI, AuthenticationError
from openai.types.chat import ChatCompletion
from openai.types.responses import (
    Response, ResponseReasoningItem, ResponseOutputText, ResponseCreatedEvent,
    ResponseOutputItemAddedEvent, ResponseInProgressEvent, ResponseOutputItemDoneEvent,
    ResponseTextDeltaEvent, ResponseFunctionToolCall, ResponseFunctionCallArgumentsDoneEvent,
    ResponseCompletedEvent
)

from openai.types.responses.response_function_call_arguments_delta_event import ResponseFunctionCallArgumentsDeltaEvent
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Self
import tiktoken

class OpenAiLlm(LlmBaseProvider):
    base_url :Optional[str]=None
    _use_responses_api :Optional[bool]=None

    @model_validator(mode="after")
    def set_openai(self)->Self:

        self.client :OpenAI = OpenAI(
            api_key=self.config.api_key,
            base_url=self.base_url or self.config.base_url
        )
        _aclient :AsyncOpenAI = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.base_url or self.config.base_url
        )
        self._auth_exception = AuthenticationError
        self.validate_config()
        self.aclient = _aclient
        
        if self.use_responses_api:
            self.completion_fn = self.client.responses.create
            self.acompletion_fn = _aclient.responses.create
        else:
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
        if self.use_responses_api:
            return self.normalize_responses(response=chunk, completion_id=completion_id)

        usage = chunk.usage
        if usage is not None:
            cached_tokens = usage.prompt_tokens_details.cached_tokens \
            if usage.prompt_tokens_details is not None \
            else 0
            ### https://platform.openai.com/docs/guides/prompt-caching
            self.usage.record_completion(
                prompt_tokens=usage.prompt_tokens-cached_tokens,
                response_tokens=usage.completion_tokens,
                cached_tokens=cached_tokens,
                completion_id=completion_id or chunk.id
            )
        ### choices is not available either, mght as well make a normalize responses fn at this point
        return chunk.choices

    def normalize_responses(self, response :Union[
        Response, ResponseCreatedEvent, ResponseOutputItemAddedEvent, 
        ResponseInProgressEvent, ResponseOutputItemDoneEvent, ResponseTextDeltaEvent
        ],
        completion_id :Optional[str]=None
    )->List[Union[ResponseReasoningItem, ResponseOutputText]]:

        if isinstance(response, (Response, ResponseCompletedEvent)):
            if isinstance(response, ResponseCompletedEvent):
                response = response.response
                response.output = "" ### we already build the output from the chunks
            # No stream scenario
            usage = response.usage
            if usage is not None:
                cached_tokens = usage.input_tokens_details.cached_tokens \
                if usage.input_tokens_details is not None \
                else 0

                # TODO consider if we wnat to store reasoning tokens
                self.usage.record_completion(
                    prompt_tokens=usage.input_tokens-cached_tokens,
                    response_tokens=usage.output_tokens,
                    cached_tokens=cached_tokens,
                    completion_id=completion_id or response.id
                )
            return response.output_text

        if isinstance(response, ResponseTextDeltaEvent):
            return response
        
        elif isinstance(response, ResponseFunctionCallArgumentsDeltaEvent):
            return response
        
        elif isinstance(response, ResponseFunctionToolCall):
            return response
        
        elif isinstance(response, ResponseOutputItemAddedEvent) and isinstance(response.item, ResponseFunctionToolCall):
            return response.item
        
        return response
    
    def _no_stream(self, response) -> Union[str, ToolCalls]:
        if self.use_responses_api:
            message = self.normalize_fn(response)
            return message
            # # TODO add support to handle tool calls
            # _chunk = self.normalize_fn(response)
            # message = self._chunk_from_provider(_chunk).message
            # if hasattr(message, "tool_calls") and message.tool_calls:
            #     return ToolCalls(root=[
            #         self._fill_tool_schema(tool_call) for tool_call in message.tool_calls
            #     ])
            # else:
            #     return message.content

        return super()._no_stream(response=response)

    
    # TODO might need to override these
    def _handle_stream_messages(self, _chunk, message, _skip=False)->bool:
        """Handle streamed messages from synchronous completions.
        
        Args:
            _chunk: Raw message chunk
            message: Accumulated message
            _skip: Whether to skip current chunk
            
        Returns:
            bool: Updated skip state
        """
        if self.use_responses_api:
            if isinstance(_chunk, str):
                chunk_message = _chunk
            elif hasattr(_chunk, "delta"):
                chunk_message = _chunk.delta
            else:
                chunk_message = ""

            default_stream_handler(chunk_message)
            return self._handle_reasoning_steps(chunk_message, message, _skip)

        return super()._handle_stream_messages(_chunk=_chunk, message=message, _skip=_skip)
    
    async def _handle_astream_messages(self, _chunk, logger_fn, message, _skip=False)->bool:
        """Handle streamed messages from asynchronous completions.
        
        Args:
            _chunk: Raw message chunk
            logger_fn: Async logging function
            message: Accumulated message
            _skip: Whether to skip current chunk
            
        Returns:
            bool: Updated skip state
        """
        if self.use_responses_api:
            if isinstance(_chunk, str):
                chunk_message = _chunk
            elif hasattr(_chunk, "delta"):
                chunk_message = _chunk.delta
            else:
                chunk_message = ""

            await logger_fn(chunk_message)
            return self._handle_reasoning_steps(chunk_message, message, _skip)

        return await super()._handle_astream_messages(_chunk=_chunk, logger_fn=logger_fn, message=message, _skip=_skip)

    @property
    def use_responses_api(self)->bool:
        if self._use_responses_api is not None:
            return self._use_responses_api

        elif self.config.model.startswith("o") \
            or self.config.model in OPENAI_RESPONSE_API_MODELS \
            or getattr(self.config, "use_responses_api", False):
            self._use_responses_api = True
            return True
        
        else:
            self._use_responses_api = False
            return  False

    @use_responses_api.setter
    def use_responses_api(self, value :Optional[bool]):
        self._use_responses_api = value
    
    def _is_tool_call(self, _chunk)->bool:
        if self.use_responses_api:
            if isinstance(_chunk, (ResponseFunctionToolCall, ResponseFunctionCallArgumentsDeltaEvent)):
                return True
            
        elif _chunk and hasattr(self._chunk_from_provider(_chunk).delta, "tool_calls") and self._chunk_from_provider(_chunk).delta.tool_calls:
            return True

        return False
    
    def _handle_reasoning_models(self):
        if self.use_responses_api:
            self.completion_args["temperature"] = None
            reasoning_efftort = getattr(self.config, "reasoning_efftort", None)
            if reasoning_efftort is not None:
                self.completion_args["reasoning_efftort"] = reasoning_efftort
            verbosity = getattr(self.config, "verbosity", None)
            if verbosity is not None:
                self.completion_args["verbosity"] = verbosity

    def _chunk_from_provider(self, _chunk):
        if self.use_responses_api:
            if hasattr(_chunk, "delta"):
                return _chunk.delta
            return _chunk

        return super()._chunk_from_provider(_chunk)

    def _tool_chunk_from_provider(self, _chunk ):
        if self.use_responses_api:
            if hasattr(_chunk, "delta"):
                return _chunk.delta
            return _chunk
        
        return super()._tool_chunk_from_provider(_chunk)

    def _handle_openai_response_only_models(self, args :Dict):
        if self.config.model in OPENAI_RESPONSE_API_MODELS:
            args["input"] = args.pop("messages")
            args.pop("stream_options", None)
            # args.pop("max_tokens")
            # print("here")
            args.pop("max_tokens", None)
            # args.pop("max_completion_tokens", None)
            
            # GPT 5 does not support temperature
            # args.pop("temperature")
        if self.config.model in OPENAI_NO_TEMPERATURE_MODELS:
            args.pop("temperature", None)
            # max_completion_tokens should be mapped to  max_output_tokens
            # https://platform.openai.com/docs/guides/migrate-to-responses
            # Output verbosity
            # Reasoning depth:
            
        # print(json.dumps(args, indent=4))


    def _to_provider_tool_schema(self, tool: ToolSchema) -> Dict[str, Any]:
        """
        Convert to OpenAi tool schema format.
        
        Returns:
            Dictionary in OpenAi tool schema format
        """
        if self.use_responses_api:
            return {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": tool.input_schema.type,
                    "properties": tool.input_schema.properties.model_dump(),
                    "required": tool.input_schema.required,
                    **{k: v for k, v in tool.input_schema.model_dump().items() 
                    if k not in ["type", "properties", "required"]}
                }
            }

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": tool.input_schema.type,
                    "properties": tool.input_schema.properties.model_dump(),
                    "required": tool.input_schema.required,
                    **{k: v for k, v in tool.input_schema.model_dump().items() 
                       if k not in ["type", "properties", "required"]}
                }
            }
        }

    def _to_provider_tool_call_schema(self, toolCallSchema :ToolCallSchema)->ToolCallSchema:
        if self.use_responses_api:
            toolCallSchema._raw = {
                "type": "function_call",
                "name": toolCallSchema.name,
                "arguments": toolCallSchema.arguments_as_string(),
                "call_id": toolCallSchema.id
            }

        else:
            toolCallSchema._raw = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": toolCallSchema.id,
                        "function": {
                            "name": toolCallSchema.name,
                            "arguments": toolCallSchema.arguments_as_string()
                        },
                        "type": "function"
                    }
                ]
            }
        
        # ChatCompletionMessage(
        #     role="assistant",
        #     tool_calls=[
        #         ChatCompletionMessageToolCall(
        #             id=toolCallSchema.id,
        #             function=Function(
        #                 name=toolCallSchema.name,
        #                 arguments=toolCallSchema.arguments
        #             ),
        #             type="function"
        #         )
        #     ]
        # )

        return toolCallSchema

    def _tool_call_change_condition(self, tool_chunk)->bool:
        if self.use_responses_api:
            if isinstance(tool_chunk, ResponseFunctionCallArgumentsDoneEvent):
                return True
            return False
        return super()._tool_call_change_condition(tool_chunk)
    
    def _handle_tool_call_stream(self, tool_call :ToolCallSchema, tool_chunk :Union[str, ResponseFunctionToolCall])->ToolCallSchema:
        if self.use_responses_api:
            # tool_call._raw.arguments += tool_call
            if isinstance(tool_chunk, ResponseFunctionToolCall):
                tool_chunk = ""

            tool_call.arguments += tool_chunk 
            return tool_call

        tool_call._raw.arguments += tool_chunk.function.arguments
        tool_call.arguments += tool_chunk.function.arguments
        return tool_call
    
    def _fill_tool_schema(self, tool_chunk)->ToolCallSchema:
        if self.use_responses_api:
            tool_chunk : ResponseFunctionToolCall = tool_chunk
            tool_call = ToolCallSchema(
                id=tool_chunk.id,
                name=tool_chunk.name,
                arguments=tool_chunk.arguments
            )
            # tool_call._raw = ""
            return tool_call
            
        return super()._fill_tool_schema(tool_chunk)

    
    def _tool_call_message(self, toolCallSchema :ToolCallSchema, content :str) -> Dict[str, str]:
        if self.use_responses_api:
            return {
                "type": "function_call_output",
                "call_id": toolCallSchema.id,
                "output": str(content),
            }
        return {
            "type": "function_call_output",
            "role": "tool",
            "tool_call_id": toolCallSchema.id,
            "content": str(content)
        }

    def _validte_message_dict(self, message_dict: Dict[str, str]) -> bool:
        """Validate message dictionary structure.
        
        Args:
            message_dict: Message dictionary to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            AssertionError: If message structure is invalid
        """
        if self.use_responses_api:
            ### TODO add protection here later
            return True

        assert message_dict.get("role") in ["user", "system", "assistant", "tool", "developer"], f"{message_dict} 'role' attribute must be one of ['user', 'system', 'assistant', 'tool]"
        assert message_dict.get("content") is not None or message_dict.get("tool_calls") is not None, f"{message_dict} 'content' or 'tool_calls' attribute is missing"
        return True
