from typing import Literal, Optional, Self
from pydantic import BaseModel, field_validator, model_validator, ConfigDict

from aicore.const import SUPPORTED_REASONER_PROVIDERS, SUPPORTED_REASONER_MODELS
from aicore.models_metadata import METADATA, PricingConfig

class LlmConfig(BaseModel):
    provider :Literal["anthropic", "gemini", "groq", "mistral", "nvidia", "openai", "openrouter", "deepseek", "grok"]
    api_key :str
    model :str
    base_url :Optional[str]=None
    temperature :float=0
    max_tokens :int=12000
    reasoner :Optional["LlmConfig"]=None
    pricing :Optional[PricingConfig]=None
    _context_window :Optional[int]=None

    model_config = ConfigDict(
        extra="allow",
    )

    @field_validator("temperature")
    @classmethod
    def ensure_temperature_lower_than_unit(cls, temperature :float)->float:
        assert 0 <= temperature <= 1, "temperature should be between 0 and 1"
        return temperature
    
    @field_validator("reasoner", mode="after")
    @classmethod
    def ensure_valid_reasoner(cls, reasoner :"LlmConfig")->"LlmConfig":
        if isinstance(reasoner, LlmConfig):
            assert reasoner.provider in SUPPORTED_REASONER_PROVIDERS, f"{reasoner.provider} is not supported as a reasoner provider. Supported providers are {SUPPORTED_REASONER_PROVIDERS}"
            assert reasoner.model in SUPPORTED_REASONER_MODELS, f"{reasoner.model} is not supported as a reasoner model. Supported models are {SUPPORTED_REASONER_MODELS}"
        return reasoner
    
    @property
    def provider_model(self)->str:
        return f"{self.provider}-{self.model}"
    
    @property
    def context_window(self)->int:
        return self._context_window
    
    @context_window.setter
    def context_window(self, value :int):
        self._context_window = value

    @model_validator(mode="after")
    def initialize_pricing_from_defaults(self)->Self:
        model_metadata =  METADATA.get(self.provider_model)
        if model_metadata is not None:
            if self.pricing is None and model_metadata.pricing is not None:
                self.pricing = model_metadata.pricing
            if self.max_tokens > model_metadata.max_tokens:
                self.max_tokens = model_metadata.max_tokens
            if self.context_window is None and model_metadata.context_window:
                self.context_window = model_metadata.context_window
        
        return self