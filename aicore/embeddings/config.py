from typing import Literal, Optional
from pydantic import BaseModel
from aicore.pricing import PricingConfig

class EmbeddingsConfig(BaseModel):
    provider :Literal["gemini", "groq", "mistral", "nvidia", "openai"]
    api_key :str
    model :Optional[str]=None
    base_url :Optional[str]=None    
    pricing :Optional[PricingConfig]=None