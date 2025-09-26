from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.llm.mcp.models import ToolCallSchema, ToolSchema
from aicore.const import OPENAI_RESPONSE_API_MODELS, OPENAI_RESPONSE_ONLY_MODELS
from pydantic import model_validator
from openai import OpenAI, AsyncOpenAI, AuthenticationError
from openai.types.chat import ChatCompletion
from openai.types.responses import Response, ResponseReasoningItem, ResponseOutputText
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Self
import tiktoken

class OpenAiLlm(LlmBaseProvider):
    base_url :Optional[str]=None

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
        
        if self.config.model in OPENAI_RESPONSE_ONLY_MODELS:
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
        if self._needs_responses_api():
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
    
    #TODO revisit this with streaming enabled as text_output should contain a delta
    def normalize_responses(self, response :Response, completion_id :Optional[str]=None)->List[Union[ResponseReasoningItem, ResponseOutputText]]:
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
        # print(f"{response.output}")
        # print(f"\n\n{response.output_text=}")
        return response.output_text
    
    def _no_stream(self, response) -> Union[str, ToolCalls]:
        if self._needs_responses_api():
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
    def _handle_reasoning_models(self):
        if self._needs_responses_api():
            self.completion_args["temperature"] = None
            self.completion_args["max_tokens"] = None
            self.completion_args["max_completion_tokens"] = self.config.max_tokens
            reasoning_efftort = getattr(self.config, "reasoning_efftort", None)
            if reasoning_efftort is not None:
                self.completion_args["reasoning_efftort"] = reasoning_efftort

    def _handle_openai_response_only_models(self, args :Dict):
        if self.config.model in OPENAI_RESPONSE_API_MODELS:
            args["input"] = args.pop("messages")
            args.pop("stream_options", None)
            # args.pop("max_tokens")
            # print("here")
            args.pop("max_tokens", None)
            args.pop("max_completion_tokens", None)
            
            # GPT 5 does not support temperature
            # args.pop("temperature")
        if self.config.model in OPENAI_NO_TEMPERATURE_MODELS:
            args.pop("temperature", None)
            # max_completion_tokens should be mapped to  max_output_tokens
            # https://platform.openai.com/docs/guides/migrate-to-responses
            # Output verbosity
            # Reasoning depth:
            
        # print(json.dumps(args, indent=4))


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
    
    def _tool_call_message(self, toolCallSchema :ToolCallSchema, content :str) -> Dict[str, str]:
        return {
            "type": "function_call_output",
            "role": "tool",
            "tool_call_id": toolCallSchema.id,
            "content": str(content)
        }