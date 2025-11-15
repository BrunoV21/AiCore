from aicore.llm.providers.openai import OpenAiLlm

class ZaiLlm(OpenAiLlm):
    
    base_url :str="https://api.z.ai/api/paas/v4/"