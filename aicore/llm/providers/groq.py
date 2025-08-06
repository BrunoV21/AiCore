from aicore.llm.mcp.models import ToolCallSchema, ToolSchema
from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.const import GROQ_OPEN_AI_OSS_MODELS
from pydantic import model_validator
from groq import Groq, AsyncGroq, AuthenticationError
from groq.types.chat import ChatCompletionChunk
from typing import Any, Dict, Optional
from typing_extensions import Self
import tiktoken

class GroqLlm(LlmBaseProvider):

    @model_validator(mode="after")
    def set_groq(self)->Self:

        self.client :Groq = Groq(
            api_key=self.config.api_key
        )
        self._auth_exception = AuthenticationError
        self.validate_config()
        _aclient = AsyncGroq(
            api_key=self.config.api_key
        )
        self.aclient :AsyncGroq = _aclient

        self.completion_fn = self.client.chat.completions.create
        self.acompletion_fn = _aclient.chat.completions.create

        self.normalize_fn = self.normalize

        self.tokenizer_fn = tiktoken.encoding_for_model(
            self.get_default_tokenizer(
                self.config.model
            )
        ).encode

        self._handle_reasoning_models()

        return self
    
    def normalize(self, chunk :ChatCompletionChunk, completion_id :Optional[str]=None):
        x_usage = chunk.x_groq
        if x_usage is not None and getattr(x_usage, "usage", None) is not None:
            self.usage.record_completion(
                prompt_tokens=x_usage.usage.prompt_tokens,
                response_tokens=x_usage.usage.completion_tokens,
                completion_id=completion_id or chunk.id
            )
        # for now if the answer is in json groq does not return any type of usage in x_usage for openai oss models
        # possible cause bellow
        # Note: For a limited time, tool calls used with OpenAI's open models will not be charged. Learn more at groq.com/pricing.

        return chunk.choices
    
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
            "role": "tool",
            "tool_call_id": toolCallSchema.id,
            "content": str(content)
        }
    
    def _handle_reasoning_models(self):
        ### gpt oss series models series models
        if self.config.model in GROQ_OPEN_AI_OSS_MODELS:
            # self.completion_args["temperature"] = None
            self.completion_args["max_tokens"] = None
            self.completion_args["max_completion_tokens"] = self.config.max_tokens
            reasoning_efftort = getattr(self.config, "reasoning_efftort", None)
            if reasoning_efftort is not None:
                self.completion_args["reasoning_efftort"] = reasoning_efftort