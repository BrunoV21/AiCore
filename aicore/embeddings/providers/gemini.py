from aicore.embeddings.providers.openai import OpenAiEmbeddings

class GeminiEmbeddings(OpenAiEmbeddings):
    vector_dimensions :int=768
    base_url :str="https://generativelanguage.googleapis.com/v1beta/openai/"