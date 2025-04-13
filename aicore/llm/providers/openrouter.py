from aicore.llm.providers.openai import OpenAiLlm

class OpenRouterLlm(OpenAiLlm):
    
    base_url :str="https://openrouter.ai/api/v1"