from aicore.llm.providers.openai import OpenAiLlm

class GeminiLlm(OpenAiLlm):
    base_url :str="https://generativelanguage.googleapis.com/v1beta/openai/"