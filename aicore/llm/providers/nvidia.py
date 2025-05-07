from aicore.llm.providers.openai import OpenAiLlm
from typing import Optional, List, Dict
from typing_extensions import Self

class NvidiaLlm(OpenAiLlm):
    """
    most nvidia hosted models are limited to 4K max output tokens
    """
    
    base_url :str="https://integrate.api.nvidia.com/v1"

    @staticmethod
    def _message_content(prompt :str, img_b64_str :Optional[List[str]]=None)->List[Dict]:
        if img_b64_str is not None:
            raise ValueError("Nvidia hosted models do not support images uplaod via OpenAi compatible requests.")

        return prompt