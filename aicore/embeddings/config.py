from typing import Literal, Optional
from pydantic import BaseModel

class EmbeddingsConfig(BaseModel):
    provider :Literal["groq", "mistral", "openai"]
    api_key :str
    model :Optional[str]=None
    base_url :Optional[str]=None