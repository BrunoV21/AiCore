from aicore.llm.mcp.models import ToolCallSchema, ToolCalls, ToolSchema
from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.logger import default_stream_handler
from aicore.const import STREAM_START_TOKEN, STREAM_END_TOKEN, REASONING_STOP_TOKEN, TOOL_CALL_START_TOKEN
from pydantic import model_validator
# from mistral_common.protocol.instruct.messages import UserMessage
# from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
from mistralai import Mistral, CompletionEvent, CompletionResponseStreamChoice, models
from typing import Any, Optional, Union, List, Literal, Dict
from typing_extensions import Self
import tiktoken

#TODO replace Tiktoken with Mistral tekken encoder when it is updated to work on python 3.13#
class MistralLlm(LlmBaseProvider):

    @model_validator(mode="after")
    def set_mistral(self)->Self:

        self.client :Mistral = Mistral(
            api_key=self.config.api_key
        )
        self._auth_exception = models.SDKError
        self.validate_config()
        ### Suspect Misral will always stream by default
        self.completion_fn = self.client.chat.stream
        self.acompletion_fn = self.client.chat.stream_async
        self.normalize_fn = self.normalize
        self.tokenizer_fn = tiktoken.encoding_for_model(
            self.get_default_tokenizer(
                self.config.model
            )
        ).encode

        return self
    
    def normalize(self, chunk:CompletionEvent, completion_id :Optional[str]=None)->CompletionResponseStreamChoice:
        data = chunk.data
        # print(f"{data=}")
        if data.usage is not None:
            self.usage.record_completion(
                prompt_tokens=data.usage.prompt_tokens,
                response_tokens=data.usage.completion_tokens,
                completion_id=completion_id or data.id
            )
        return data.choices
    
    def _message_body(self, prompt: Union[List[str], str], role: Literal["user", "system", "assistant"] = "user", img_b64_str: Optional[List[str]] = None, _last: Optional[bool] = False) -> Dict:
        message_body = {
            "role": role,
            "content": self._message_content(prompt, img_b64_str)
        }
        if role == "assistant" and _last:
            message_body["prefix"] = True
        return message_body
    
    def _stream(self, stream, prefix_prompt :Optional[Union[str, List[str]]]=None)->str:
        message = []

        prefix_prompt = "".join(prefix_prompt) if isinstance(prefix_prompt, list) else prefix_prompt
        prefix_buffer = []
        prefix_completed = not bool(prefix_prompt)
        for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                if prefix_completed:
                    default_stream_handler(chunk_message)
                    message.append(chunk_message)
                else:
                    prefix_buffer.append(chunk_message)
                    if "".join(prefix_buffer) == prefix_prompt:
                        prefix_completed = True
                
        if self._is_reasoner:
            default_stream_handler(REASONING_STOP_TOKEN)
        response = "".join(message)
        return response
    
    async def _astream(self, stream, logger_fn, prefix_prompt :Optional[Union[str, List[str]]]=None)->str:
        message = []
    
        await logger_fn(STREAM_START_TOKEN) if not prefix_prompt else ...

        _calling_tool = False
        tool_calls = ToolCalls()

        prefix_prompt = "".join(prefix_prompt) if isinstance(prefix_prompt, list) else prefix_prompt
        prefix_buffer = []
        prefix_completed = not bool(prefix_prompt)
        
        async for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                if prefix_completed and isinstance(chunk_message, str):
                    await logger_fn(chunk_message)
                    message.append(chunk_message)
                elif isinstance(chunk_message, list):
                    ### ignore aditional mistral information like citations for now
                    pass
                else:
                    prefix_buffer.append(chunk_message)
                    if "".join(prefix_buffer) == prefix_prompt:
                        prefix_completed = True
                        await logger_fn(STREAM_START_TOKEN)

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
    
    @staticmethod
    def _to_provider_tool_schema(tool: ToolSchema) -> Dict[str, Any]:
        """
        Convert to OpenAi tool schema format.
        
        Returns:
            Dictionary in OpenAi tool schema format
        """
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
    
    @staticmethod
    def _to_provider_tool_call_schema(toolCallSchema :ToolCallSchema)->ToolCallSchema:
        toolCallSchema._raw = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": toolCallSchema.id,
                    "function": {
                        "name": toolCallSchema.name,
                        "arguments": toolCallSchema.arguments
                    },
                    "type": "function"
                }
            ]
        }

        return toolCallSchema
    
    def _tool_call_message(self, toolCallSchema :ToolCallSchema, content :str) -> Dict[str, str]:
        return {
            "type": "function_call_output",
            "role": "tool",
            "tool_call_id": toolCallSchema.id,
            "content": str(content)
        }