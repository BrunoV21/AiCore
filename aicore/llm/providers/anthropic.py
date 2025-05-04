from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.models import AuthenticationError
from aicore.logger import default_stream_handler
from pydantic import model_validator
from typing import Any, Optional, Dict, Union, List
from typing_extensions import Self
from anthropic import Anthropic, AsyncAnthropic, AuthenticationError
from anthropic.types import RawContentBlockStartEvent, ToolUseBlock, RawContentBlockDeltaEvent, InputJSONDelta
from functools import partial

from aicore.llm.mcp.models import ToolCallSchema, ToolCalls, ToolSchema

class AnthropicLlm(LlmBaseProvider):

    @staticmethod
    def anthropic_count_tokens(contents :str, client :AsyncAnthropic, model :str):
        """
        unfortunately system messages can not be included into the count's default method
        due to the way the tokennizer fn has been implemented in aicore
        """
        response = client.messages.count_tokens(
            model=model,
            messages=[{
                "role": "user",
                "content": contents
            }],
        )
        input_tokens = response.model_dump().get("input_tokens")
        return [i for i in range(input_tokens)] if input_tokens else []

    @model_validator(mode="after")
    def set_anthropic(self)->Self:
        _client :Anthropic = Anthropic(
            api_key=self.config.api_key
        )
        self.client :Anthropic = _client
        self._auth_exception = AuthenticationError
        self.validate_config()
        _aclient :AsyncAnthropic = AsyncAnthropic(
            api_key=self.config.api_key
        )
        self._aclient = _aclient
        self.completion_fn = _client.messages.create
        self.acompletion_fn = _aclient.messages.create
        self.normalize_fn = self.normalize

        self.tokenizer_fn = partial(
            self.anthropic_count_tokens,
            client=_client,
            model=self.config.model
        )

        self._handle_thinking_models()

        return self

    def normalize(self, event, completion_id :Optional[str]=None):
        """  async for event in stream:
            event_type = event.type
            if event_type == "message_start":
                usage.input_tokens = event.message.usage.input_tokens
                usage.output_tokens = event.message.usage.output_tokens
            elif event_type == "content_block_delta":
                content = event.delta.text
                log_llm_stream(content)
                collected_content.append(content)
            elif event_type == "message_delta":
                usage.output_tokens = event.usage.output_tokens  # update final output_tokens
        """
        event_type = event.type
        input_tokens = 0
        output_tokens = 0
        print(event)
        if event_type == "message_start":
            input_tokens = event.message.usage.input_tokens
            output_tokens = event.message.usage.output_tokens
            cache_write_tokens = event.message.usage.cache_creation_input_tokens
            cached_tokens = event.message.usage.cache_read_input_tokens
            ### https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
            self.usage.record_completion(
                prompt_tokens=input_tokens,
                response_tokens=output_tokens,
                cached_tokens=cached_tokens,
                cache_write_tokens=cache_write_tokens,
                completion_id=completion_id or event.message.id
            )
        elif event_type == "content_block_delta":
            return event
        elif event_type == "content_block_start" and isinstance(getattr(event, "content_block", None), ToolUseBlock):
            return event
        elif event_type == "message_delta":
            output_tokens = event.usage.output_tokens
            self.usage.record_completion(
                prompt_tokens=0,
                response_tokens=output_tokens,
                completion_id=completion_id
            )

    @staticmethod
    def _chunk_from_provider(_chunk :RawContentBlockStartEvent):
        return _chunk
    
    
    @classmethod
    def _tool_chunk_from_provider(cls, _chunk):
        if isinstance(_chunk, RawContentBlockStartEvent) and isinstance(_chunk.content_block, ToolUseBlock):
            return _chunk.content_block
        elif isinstance(_chunk, RawContentBlockDeltaEvent) and isinstance(_chunk.delta, InputJSONDelta):
            return _chunk.delta
        
    @staticmethod
    def _fill_tool_schema(tool_chunk)->ToolCallSchema:
        tool_call = ToolCallSchema(
            id=tool_chunk.id,
            name=tool_chunk.name,
            arguments=""#tool_chunk.function.arguments
        )
        #tool_call._raw = tool_chunk.function
        return tool_call
    
    @staticmethod
    def _tool_call_change_condition(tool_chunk)->bool:
        return isinstance(tool_chunk, ToolUseBlock)
    
    @staticmethod
    def _handle_tool_call_stream(tool_call :ToolCallSchema, tool_chunk)->ToolCallSchema:
        tool_call.arguments += tool_chunk.partial_json
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

    @classmethod
    def _is_tool_call(cls, _chunk)->bool:
        print(f"{_chunk=}")
        print(f"{type(_chunk)=}\n")
        if isinstance(_chunk, RawContentBlockStartEvent) and isinstance(_chunk.content_block, ToolUseBlock):
            print("HERE TOOL_CALL START")
            return True
        elif isinstance(_chunk, RawContentBlockDeltaEvent) and isinstance(_chunk.delta, InputJSONDelta):
            print("HERE TOOL_CALL DELTA")
            return True
        
        # hasattr(cls._chunk_from_provider(_chunk).delta, "tool_calls") and cls._chunk_from_provider(_chunk).delta.tool_calls:
            # return True
        return False

    @classmethod
    def _handle_stream_messages(cls, event, message, _skip=False)->bool:
        if hasattr(event, "delta"):
            delta = event.delta
            chunk_message = getattr(delta, "text", "")
            chunk_thinking = getattr(delta, "thinking", None)
            chunk_signature = getattr(delta, "signature", None)
            chunk_stream = chunk_message or chunk_thinking or chunk_signature
            default_stream_handler(chunk_stream)
            if chunk_stream:
                if chunk_message:
                    message.append(chunk_message)
        return False
    
    @classmethod
    async def _handle_astream_messages(cls, event, logger_fn, message, _skip=False)->bool:
        if hasattr(event, "delta"):
            delta = event.delta
            chunk_message = getattr(delta, "text", "")
            chunk_thinking = getattr(delta, "thinking", None)
            chunk_signature = getattr(delta, "signature", None)
            chunk_stream = chunk_message or chunk_thinking or chunk_signature
            if chunk_stream:
                await logger_fn(chunk_stream)
                if chunk_message:
                    message.append(chunk_message)
        return False

    def _handle_system_prompt(self,
            messages :list,
            system_prompt: Optional[Union[List[str], str]] = None):
        pass

    def _handle_special_sys_prompt_anthropic(self, args :Dict, system_prompt: Optional[Union[List[str], str]] = None):
        if system_prompt:
            if getattr(self.config, "cache_control", None):
                cached_system_prompts_index :list = getattr(self.config, "cache_control")
                assert isinstance(cached_system_prompts_index, list), "cache_control param must be a list of ints"
                system_prompt = [system_prompt] if isinstance(system_prompt, str) else system_prompt
                processed_system_prompts = []
                for i, prompt in enumerate(system_prompt):
                    prompt =  {
                        "type": "text",
                        "text": prompt,
                    }
                    if i in cached_system_prompts_index:
                        prompt["cache_control"] = {"type": "ephemeral"}
                    processed_system_prompts.append(prompt)
                args["system"] = processed_system_prompts
            else:
                args["system"] = "\n".join(system_prompt) if isinstance(system_prompt, list) else system_prompt

    def _handle_thinking_models(self):
        thinking = getattr(self.config, "thinking", None)
        if thinking:
            if isinstance(thinking, bool):
                self.completion_args["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.config.max_tokens
                }
            elif isinstance(thinking, dict):
                self.completion_args["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": thinking.get("budget_tokens") or self.config.max_tokens
                }

    @staticmethod
    def _to_provider_tool_schema(tool: ToolSchema) -> Dict[str, Any]:
        """
        Convert to Anthropic tool schema format.
        
        Returns:
            Dictionary in Anthropic tool schema format
        """
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": tool.input_schema.type,
                "properties": tool.input_schema.properties.model_dump(),
                "required": tool.input_schema.required,
                **{k: v for k, v in tool.input_schema.model_dump().items() 
                   if k not in ["type", "properties", "required"]}
            }
        }
    
    @staticmethod
    def _to_provider_tool_call_schema(toolCallSchema :ToolCallSchema)->ToolCallSchema:
        """
        https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview#single-tool-example
        """

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