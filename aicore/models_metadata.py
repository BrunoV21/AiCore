from pydantic import BaseModel, model_validator
from datetime import datetime, timedelta
from typing import Optional, Dict
import pytz
import json

from aicore.const import METADATA_JSON, DEFAULT_ENCODING

with open(METADATA_JSON, "r", encoding=DEFAULT_ENCODING) as _file:    
    ### https://www.anthropic.com/pricing#anthropic-api
    ### https://openai.com/api/pricing/    
    ### https://mistral.ai/products/la-plateforme#pricing
    ### https://groq.com/pricing/    
    ### https://api-docs.deepseek.com/quick_start/pricing
    MODELS_METADATA: Dict = json.load(_file)

class HappyHour(BaseModel):
    start: datetime
    finish: datetime
    pricing: "PricingConfig"

    @model_validator(mode="before")
    @classmethod
    def parse_time_strings(cls, kwargs: dict) -> dict:
        parsed_args = {}
        for key, value in kwargs.items():
            if key == "pricing":
                parsed_args[key] = value
                continue

            if isinstance(value, datetime):
                # If already a datetime, ensure it's pytz.UTC
                if value.tzinfo is None:
                    parsed_args[key] = value.replace(tzinfo=pytz.UTC)
                    continue
                parsed_args[key] = value.astimezone(pytz.UTC)
                
            elif isinstance(value, str):
                try:
                    # Parse time string (e.g. "16:30")
                    time_obj = datetime.strptime(value, "%H:%M").time()
                    # Get today's date in pytz.UTC
                    today = datetime.now(pytz.UTC).date()
                    # Combine date and time
                    naive_dt = datetime.combine(today, time_obj)
                    # Handle overnight case (e.g. finish time is next day)
                    if key == 'finish' and time_obj.hour < 12:
                        naive_dt += timedelta(days=1)
                    # Make timezone aware
                    parsed_args[key] = naive_dt.replace(tzinfo=pytz.UTC)
                    
                except ValueError as e:
                    raise ValueError(f"Invalid time format: {value}. Expected HH:MM") from e
                        
        return parsed_args

class DynamicPricing(BaseModel):
    threshold: int
    pricing: "PricingConfig"

    @model_validator(mode="after")
    def validate_threshold(self) -> "DynamicPricing":
        if self.threshold <= 0:
            raise ValueError("Dynamic pricing threshold must be positive")
        return self

class PricingConfig(BaseModel):
    """
    pricing ($) per 1M tokens
    """
    input: float
    output: float = 0
    cached: float = 0
    cache_write: float = 0
    happy_hour: Optional[HappyHour] = None
    dynamic: Optional[DynamicPricing] = None
    
    def calculate_cost(self, 
            prompt_tokens: int, 
            response_tokens: int, 
            cached_tokens: int = 0, 
            cache_write_tokens: int = 0,
            timestamp: Optional[datetime] = None
        ) -> float:
        """Calculate cost based on token counts and current pricing rules"""
        pricing = self._get_active_pricing(timestamp)
        
        cost = (pricing.input * prompt_tokens + 
                pricing.output * response_tokens + 
                pricing.cached * cached_tokens + 
                pricing.cache_write * cache_write_tokens)
        
        return cost * 1e-6  # Convert from per 1M tokens to per token

    def _get_active_pricing(self, timestamp: Optional[datetime] = None) -> "PricingConfig":
        timestamp = timestamp or datetime.now(pytz.UTC)
        if self.happy_hour and self.happy_hour.start <= timestamp <= self.happy_hour.finish:
            return self.happy_hour.pricing
        return self

class ModelMetaData(BaseModel):
    context_window: int = 128000
    max_tokens: int = 8192
    tool_use: bool = True
    pricing: Optional[PricingConfig] = None

METADATA: Dict[str, ModelMetaData] = {
    model: ModelMetaData(**metadata)
    for model, metadata in MODELS_METADATA.items()
}
