from aicore.embeddings.providers.openai import OpenAiEmbeddings
from typing import Dict

class NvidiaEmbeddings(OpenAiEmbeddings):
    vector_dimensions :int=4096
    base_url :str="https://integrate.api.nvidia.com/v1"
    _extra_body :Dict[str, str]={"input_type": "query", "truncate": "NONE"}