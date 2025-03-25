from pydantic import BaseModel

DEFAULT_PRICINGS = {
    "anthropic-claude-3-7-sonnet-latest": {"input": 3, "output": 15},
    "anthropic-claude-3-5-sonnet-latest": {"input": 3, "output": 15},
    "anthropic-claude-3-5-haiku-latest": {"input": 0., "output": 4},
    "openai-gpt-4o": {"input": 2.5, "output": 10, "cached": 1.25},
    "openai-gpt-4o-mini": {"input": 0.15, "output": 0.6, "cached": 0.075},
    "openai-gpt-4.5": {"input": 75, "output": 150, "cached": 37.5},
    "openai-o1": {"input": 15, "output": 60, "cached": 7.5},
    "openai-o3-mini": {"input": 1.1, "output": 4.40, "cached": 0.55},
    "mistral-mistral-large-latest": {"input": 2, "output": 6},
    "mistral-mistral-small-latest": {"input": 0.1, "output": 0.3},
    "mistral-pixtral-large-latest": {"input": 2, "output": 6},
    "mistral-codestral-latest": {"input": 0.3, "output": 0.9},
    "mistral-ministral-8b-latest": {"input": 0.1, "output": 0.1},
    "mistral-ministral-3b-latest": {"input": 0.04, "output": 0.04},
    "mistral-mistral-embed": {"input": 0.1, "output": 0},
    "mistral-pixtral-12b": {"input": 0.15, "output": 0.15},
    "mistral-mistral-nemo": {"input": 0.15, "output": 0.15},
    "gemini-gemini-2.5-pro-exp-03-25": {"input": 0, "output": 0},
    "gemini-gemini-2.0-flash-exp": {"input": 0, "output": 0},
    "gemini-gemini-2.0-flash-thinking-exp-01-21": {"input": 0, "output": 0},
    "gemini-gemini-2.0-flash": {"input": 0.10, "output": 0.4},
    "gemini-gemini-2.0-flash-lite": {"input": 0.075, "output": 0.3}
}

class PricingConfig(BaseModel):
    """
    pricing ($) per 1M tokens
    """
    input :float
    output :float=0

    @classmethod
    def from_model_providers(cls, model :str, provider :str)->"PricingConfig":
        model_provider_str = f"{provider}-{model}"
        if model_provider_str in DEFAULT_PRICINGS:
            return cls(**DEFAULT_PRICINGS.get(model_provider_str))
        return None