from aicore.llm.mcp.models import ToolSchema
from aicore.llm.providers.openai import OpenAiLlm
from openai.types.chat import ChatCompletionChunk
from deepseek_tokenizer import ds_token
from pydantic import model_validator
from typing import Any, Dict, Optional
from typing_extensions import Self

class DeepSeekLlm(OpenAiLlm):
    """
    most nvidia hosted models are limited to 4K max output tokens
    """
    
    base_url :str="https://api.deepseek.com"

    @model_validator(mode="after")
    def pass_deepseek_tokenizer_fn(self)->Self:
        self.tokenizer_fn = ds_token.encode

        return self

    def normalize(self, chunk :ChatCompletionChunk, completion_id :Optional[str]=None):
        print(chunk,"\n")
        usage = chunk.usage
        if usage is not None:
            ### https://api-docs.deepseek.com/news/news0802
            self.usage.record_completion(
                prompt_tokens=usage.prompt_cache_miss_tokens,
                response_tokens=usage.completion_tokens,
                cached_tokens=usage.prompt_cache_hit_tokens,
                completion_id=completion_id or chunk.id
            )
        return chunk.choices

    @staticmethod
    def _to_provider_tool_schema(tool: ToolSchema) -> Dict[str, Any]:
        """
        Convert to Deepseek tool schema format.
        
        Returns:
            Dictionary in Deepseek tool schema format
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