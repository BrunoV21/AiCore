from aicore.llm.providers.openai import OpenAiLlm
from openai.types.chat import ChatCompletion
from typing import Optional

class DeepSeekLlm(OpenAiLlm):
    """
    most nvidia hosted models are limited to 4K max output tokens
    """
    
    base_url :str="https://api.deepseek.com"


    def normalize(self, chunk :ChatCompletion, completion_id :Optional[str]=None):
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