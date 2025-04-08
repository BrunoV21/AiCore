from aicore.llm.providers.openai import OpenAiLlm

class OpenRouterLlm(OpenAiLlm):
    """
    most nvidia hosted models are limited to 4K max output tokens
    """
    
    base_url :str="https://openrouter.ai/api/v1"