from pydantic import BaseModel

DEFAULT_PRICINGS = {
    "mistral-small-latest": {"input": 1, "output": 1},
    "gemini-gemini-2.0-flash-exp": {"input": 1, "output": 1}
}

class PricingConfig(BaseModel):
    """
    pricing ($) per 1M tokens
    """
    input :float
    output :float

    @classmethod
    def from_model_providers(cls, model :str, provider :str)->"PricingConfig":
        model_provider_str = f"{provider}-{model}"
        if model_provider_str in DEFAULT_PRICINGS:
            return cls(**DEFAULT_PRICINGS.get(model_provider_str))
        return None