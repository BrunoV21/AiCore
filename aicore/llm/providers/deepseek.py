from aicore.llm.mcp.models import ToolCallSchema, ToolSchema
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