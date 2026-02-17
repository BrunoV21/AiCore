from typing import List, Literal, Optional, Union, Dict
from typing_extensions import Self
from pydantic import BaseModel, field_validator, model_validator, ConfigDict, Field

from aicore.const import DEFAULT_TIMEOUT, SUPPORTED_REASONER_PROVIDERS, SUPPORTED_REASONER_MODELS
from aicore.models_metadata import METADATA, PricingConfig

class LlmConfig(BaseModel):
    provider :Literal["anthropic", "gemini", "groq", "mistral", "nvidia", "openai", "openrouter", "deepseek", "grok", "zai", "claude_code", "remote_claude_code"]
    # For remote_claude_code: api_key is used as the Bearer token for the proxy server
    api_key :Optional[str]=None
    model :str
    # For remote_claude_code: base_url is the proxy server URL (e.g. "http://localhost:8080")
    base_url :Optional[str]=None
    temperature :float=0
    max_tokens :int=12000
    reasoner :Optional["LlmConfig"]=None
    pricing :Optional[PricingConfig]=None
    _context_window :Optional[int]=None

    mcp_config :Optional[str]=Field(default=None, alias="mcp_config_path")
    tool_choice :Union[str, Dict, None]=None
    max_tool_calls_per_response :Optional[int]=None
    concurrent_tool_calls :Optional[bool]=True

    timeout :Optional[int]=DEFAULT_TIMEOUT
    tool_use :Optional[bool]=None
    
    # claude_code-specific fields (ignored by other providers)
    permission_mode: Optional[str] = None
    cwd: Optional[str] = None
    max_turns: Optional[int] = None
    allowed_tools: Optional[List[str]] = None
    # cli_path is a server-side concern; RemoteClaudeCodeLlm ignores this field
    cli_path: Optional[str] = None
    # Note: temperature and max_tokens are ignored for the claude_code provider

    # remote_claude_code: set True to skip the startup GET /health connectivity check
    # (useful in production or when the proxy server is known to be up)
    skip_health_check: Optional[bool] = False

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
        model_metadata = METADATA.get(self.provider_model)
        if model_metadata is not None:
            if self.pricing is None and model_metadata.pricing is not None:
                if getattr(self, "use_anthropics_beta_expanded_ctx", None):
                    ...
                elif model_metadata.pricing.avoid_dynamic and model_metadata.pricing.dynamic is not None:
                    self.context_window = model_metadata.pricing.dynamic.threshold
                self.pricing = model_metadata.pricing
            if self.max_tokens > model_metadata.max_tokens:
                self.max_tokens = model_metadata.max_tokens
            if self.context_window is None and model_metadata.context_window:
                self.context_window = model_metadata.context_window
            if self.tool_use is None:
                self.tool_use = model_metadata.tool_use
        
        return self
    
    @field_validator("tool_choice", mode="before")
    @classmethod
    def auto_tool_choice_from_mcp(cls, kwargs :Dict)->Dict:
        if kwargs and kwargs.get("mcp_config_path") and not kwargs.get("tool_choice"):
            kwargs["tool_choice"] = "auto"
        return kwargs
    
    def set_anthropics_beta_context(self):        
        model_metadata = METADATA.get(self.provider_model)
        self.use_anthropics_beta_expanded_ctx = True
        self.context_window = model_metadata.context_window
