from typing import Literal, Optional
from pydantic import BaseModel, field_validator

class LlmConfig(BaseModel):
    provider :Literal["gemini", "groq", "mistral", "nvidia", "openai"]
    api_key :str
    model :Optional[str]=None
    base_url :Optional[str]=None
    temperature :float=0
    max_tokens :int=124000

    @field_validator("temperature")
    @classmethod
    def ensure_temperature_lower_than_unit(cls, temperature :float)->float:
        assert 0 <= temperature <= 1, "temperature should be between 0 and 1"
        return temperature

    