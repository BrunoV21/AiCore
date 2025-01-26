from aicore.llm.providers.openai import OpenAiLlm

class NvidiaLlm(OpenAiLlm):
    base_url :str="https://integrate.api.nvidia.com/v1"