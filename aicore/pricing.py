from pydantic import BaseModel, model_validator
from datetime import datetime, timedelta
from typing import Optional, Any
import pytz

DEFAULT_PRICINGS = {
    ### https://www.anthropic.com/pricing#anthropic-api
    ### caching not taken into account
    "anthropic-claude-3-7-sonnet-latest": {"input": 3, "output": 15, "cached": 0.30, "cache_write": 3.75},
    "anthropic-claude-3-5-sonnet-latest": {"input": 3, "output": 15, "cached": 0.30, "cache_write": 3.75},
    "anthropic-claude-3-5-haiku-latest": {"input": 0.8, "output": 4, "cached": 1, "cache_write": 0.08},
    ### automatic caching pricing not taken into account
    ### https://openai.com/api/pricing/
    "openai-gpt-4o": {"input": 2.5, "output": 10, "cached": 1.25},
    "openai-gpt-4o-mini": {"input": 0.15, "output": 0.6, "cached": 0.075},
    "openai-gpt-4.5": {"input": 75, "output": 150, "cached": 37.5},
    "openai-o1": {"input": 15, "output": 60, "cached": 7.5},
    "openai-o3-mini": {"input": 1.1, "output": 4.40, "cached": 0.55},
    ### https://mistral.ai/products/la-plateforme#pricing
    "mistral-mistral-large-latest": {"input": 2, "output": 6},
    "mistral-mistral-small-latest": {"input": 0.1, "output": 0.3},
    "mistral-pixtral-large-latest": {"input": 2, "output": 6},
    "mistral-codestral-latest": {"input": 0.3, "output": 0.9},
    "mistral-ministral-8b-latest": {"input": 0.1, "output": 0.1},
    "mistral-ministral-3b-latest": {"input": 0.04, "output": 0.04},
    "mistral-mistral-embed": {"input": 0.1, "output": 0},
    "mistral-pixtral-12b": {"input": 0.15, "output": 0.15},
    "mistral-mistral-nemo": {"input": 0.15, "output": 0.15},
    ### variable pricing due to inut tokens not taken into account and caching not taken into account
    "gemini-gemini-2.5-pro-exp-03-25": {"input": 0, "output": 0},
    "gemini-gemini-2.0-flash-exp": {"input": 0, "output": 0},
    "gemini-gemini-2.0-flash-thinking-exp-01-21": {"input": 0, "output": 0},
    "gemini-gemini-2.0-flash": {"input": 0.10, "output": 0.4},
    "gemini-gemini-2.0-flash-lite": {"input": 0.075, "output": 0.3},
    "gemini-gemini-2.5-pro-preview-03-25": {"input": 1.25, "output": 10, "dynamic": {"threshold": 200000, "pricing": {"input": 2.5, "output": 15}}},
    ### https://groq.com/pricing/
    "groq-meta-llama/llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "groq-meta-llama/llama-4-maverick-17b-128e-instruct": {"input": 0.5, "output": 0.77},
    "groq-deepseek-r1-distill-llama-70b": {"input": 0.75, "output": 0.99},
    "groq-deepseek-r1-distill-qwen-32b": {"input": 0.69, "output": 0.69},
    "groq-qwen-2.5-32b": {"input": 0.79, "output": 0.79},
    "groq-qwen-2.5-coder-32b": {"input": 0.79, "output": 0.79},
    "groq-qwen-qwq-32b": {"input": 0.29, "output": 0.39},
    "groq-mistral-saba-24b": {"input": 0.79, "output": 0.79},
    ### daily discount time and caching not taken into account
    ### https://api-docs.deepseek.com/quick_start/pricing
    "deepseek-deepseek-reasoner": {"input": 0.55, "output": 2.10, "cached": 0.14, "happy_hour": {"start": "16:30", "finish": "00:30", "pricing": {"input": 0.135, "output": 0.55, "cached": 0.035}}},
    "deepseek-deepseek-chat": {"input": 0.27, "output": 1.10, "cached": 0.07, "happy_hour": {"start": "16:30", "finish": "00:30", "pricing": {"input": 0.135, "output": 0.55, "cached": 0.035}}}
}

class HappyHour(BaseModel):
    start :datetime
    finish :datetime
    pricing :"PricingConfig"

    @model_validator( mode="before")
    @classmethod
    def parse_time_strings(cls, kwargs: dict) -> dict:
        parsed_args = {}
        for key, value in kwargs.items():
            if key == "pricing":
                parsed_args[key] = value
                continue

            if isinstance(value, datetime):
                # If already a datetime, ensure it's UTC
                if value.tzinfo is None:
                    parsed_args[key] = value.replace(tzinfo=pytz.UTC)
                    continue
                parsed_args[key] = value.astimezone(pytz.UTC)
                
            elif isinstance(value, str):
                try:
                    # Parse time string (e.g. "16:30")
                    time_obj = datetime.strptime(value, "%H:%M").time()
                    # Get today's date in UTC
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
    threshold :int
    pricing :"PricingConfig"

class PricingConfig(BaseModel):
    """
    pricing ($) per 1M tokens
    """
    input :float
    output :float=0
    cached :float=0
    cache_write :float=0
    happy_hour :Optional[HappyHour]=None
    dynamic :Optional[DynamicPricing]=None

    @classmethod
    def from_model_providers(cls, model :str, provider :str)->"PricingConfig":
        model_provider_str = f"{provider}-{model}"
        if model_provider_str in DEFAULT_PRICINGS:
            return cls(**DEFAULT_PRICINGS.get(model_provider_str))
        return None