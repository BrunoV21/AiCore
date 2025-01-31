from typing import Literal, Optional, Union
from pydantic import BaseModel, field_validator

from aicore.const import SUPPORTED_REASONER_PROVIDERS, SUPPORTED_REASONER_MODELS

class LlmConfig(BaseModel):
    provider :Literal["gemini", "groq", "mistral", "nvidia", "openai", "openrouter"]
    api_key :str
    model :Optional[str]=None
    base_url :Optional[str]=None
    temperature :float=0
    max_tokens :int=12000
    reasoner :Union["LlmConfig", None]=None

    @field_validator("temperature")
    @classmethod
    def ensure_temperature_lower_than_unit(cls, temperature :float)->float:
        assert 0 <= temperature <= 1, "temperature should be between 0 and 1"
        return temperature
    
    @field_validator("reasoner", mode="after")
    @classmethod
    def ensure_valid_reasoner(cls, reasoner :"LlmConfig")->"LlmConfig":
        assert reasoner.provider in SUPPORTED_REASONER_PROVIDERS, f"{reasoner.provider} is not supported as a reasoner provider. Supported providers are {SUPPORTED_REASONER_PROVIDERS}"
        assert reasoner.model in SUPPORTED_REASONER_MODELS, f"{reasoner.model} is not supported as a reasoner model. Supported models are {SUPPORTED_REASONER_MODELS}"
        return reasoner