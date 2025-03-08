from pydantic import BaseModel

DEFAULT_PRICINGS = {
    "mistral-small-latest": {"input": 0, "output": 0}
}

class PricingConfig(BaseModel):
    """
    pricing ($) per 1M tokens
    """
    input_price :float
    output_price :float

    @classmethod
    def from_model_providers(cls, model :str, provider :str)->"PricingConfig":
        model_provider_str = f"{model}-{provider}"
        if model_provider_str in DEFAULT_PRICINGS:
            return cls(**DEFAULT_PRICINGS.get(model_provider_str))
        return None