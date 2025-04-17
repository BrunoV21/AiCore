from aicore.models_metadata import PricingConfig

from pydantic import BaseModel, RootModel, Field, computed_field, model_validator
from typing import Optional, List, Union
from datetime import datetime, timezone
from collections import defaultdict
from ulid import ulid

class CompletionUsage(BaseModel):
    """Tracks token usage and cost for a single LLM completion."""
    completion_id: Optional[str] = Field(default_factory=ulid)
    prompt_tokens: int
    response_tokens: int
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    cost: Optional[float] = 0

    @property
    def input_tokens(self) -> int:
        """Returns the number of input/prompt tokens."""
        return self.prompt_tokens
    
    @property
    def output_tokens(self) -> int:
        """Returns the number of output/response tokens."""
        return self.response_tokens

    @model_validator(mode="after")
    def validate_token_counts(self) -> "CompletionUsage":
        """Validate that token counts are non-negative."""
        if self.prompt_tokens < 0 or self.response_tokens < 0:
            raise ValueError("Token counts cannot be negative")
        return self
    
    @computed_field
    def total_tokens(self) -> int:
        """Returns the total number of tokens used (input + output)."""
        return self.input_tokens + self.output_tokens
    
    def __str__(self) -> str:
        """Returns a human-readable string representation of the usage."""
        cost_prefix = f"Cost: ${self.cost} | " if self.cost else ""
        return f"{cost_prefix}Tokens: {self.total_tokens} | Prompt: {self.prompt_tokens} | Response: {self.response_tokens}"
    
    @classmethod
    def from_pricing_info(
        cls,
        completion_id: str,
        prompt_tokens: int,
        response_tokens: int,
        cached_tokens: int = 0,
        cache_write_tokens: int = 0,
        cost: Optional[float] = 0,
        pricing: Optional[PricingConfig] = None
    ) -> "CompletionUsage":
        """Creates a CompletionUsage instance with calculated cost based on pricing config."""
        if pricing is not None:
            # Apply happy hour pricing if active
            if pricing.happy_hour is not None and pricing.happy_hour.start <= datetime.now(timezone.utc) <= pricing.happy_hour.finish:
                pricing = pricing.happy_hour.pricing
            
            input_cost = pricing.input * prompt_tokens
            output_cost = pricing.output * response_tokens
            cached_cost = pricing.cached * cached_tokens
            cache_write_cost = cache_write_tokens * pricing.cache_write

            # Apply dynamic pricing only if threshold is exceeded
            if pricing.dynamic is not None:
                total_tokens = prompt_tokens + response_tokens
                if total_tokens > pricing.dynamic.threshold:
                    # Calculate how many tokens are over the threshold
                    tokens_over_threshold = total_tokens - pricing.dynamic.threshold
                    
                    # First, determine how many input tokens are over the threshold
                    input_tokens_over_threshold = max(0, prompt_tokens - pricing.dynamic.threshold)
                    
                    # Then calculate remaining tokens over threshold (must be output tokens)
                    output_tokens_over_threshold = tokens_over_threshold - input_tokens_over_threshold
                    
                    # Recalculate costs with separate pricing for tokens above and below threshold
                    input_cost = (
                        pricing.input * (prompt_tokens - input_tokens_over_threshold) +  # Base price for tokens <= threshold
                        pricing.dynamic.pricing.input * input_tokens_over_threshold      # Dynamic price for excess tokens
                    )
                    
                    output_cost = (
                        pricing.output * (response_tokens - output_tokens_over_threshold) +  # Base price for tokens <= threshold
                        pricing.dynamic.pricing.output * output_tokens_over_threshold        # Dynamic price for excess tokens
                    )

            # Final cost calculation (always includes cached/cache_write costs)
            cost = (input_cost + output_cost + cached_cost + cache_write_cost) * 1e-6

        return cls(
            completion_id=completion_id,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            cached_tokens=cached_tokens,
            cache_write_tokens=cache_write_tokens,
            cost=cost,
        )
    
    def update_with_pricing(self, pricing: PricingConfig):
        """Updates the cost based on the given pricing config if not already set. Does not take into account cost of cache writing"""
        if not self.cost:
            if pricing.happy_hour is not None and pricing.happy_hour.start <= datetime.now(timezone.utc) <= pricing.happy_hour.finish:
                pricing = pricing.happy_hour.pricing
            
            if pricing.dynamic is not None and self.prompt_tokens + self.response_tokens > pricing.dynamic.threshold:
                pricing = pricing.dynamic.pricing
            
            self.cost = (
                pricing.input * self.prompt_tokens 
                + pricing.output * self.response_tokens
                + pricing.cached * self.cached_tokens
                + pricing.cache_write * self.cache_write_tokens
            ) * 1e-6

class UsageInfo(RootModel):
    """Aggregates token usage and cost across multiple completions."""
    root: List[CompletionUsage] = []
    _pricing: Optional[PricingConfig] = None
    _allow_negative_costs: bool = False

    @classmethod
    def from_pricing_config(cls, pricing: PricingConfig) -> "UsageInfo":
        """Creates a UsageInfo instance with the given pricing config."""
        instance = cls()
        instance.pricing = pricing
        return instance

    @property
    def allow_negative_costs(self) -> bool:
        """Returns whether negative costs are allowed (for testing purposes)."""
        return self._allow_negative_costs

    def record_completion(
        self,
        prompt_tokens: int,
        response_tokens: int,
        cached_tokens: int = 0,
        cache_write_tokens: int = 0,
        completion_id: Optional[str] = None
    ):
        """Records a new completion with the given token counts."""
        if completion_id is None and self.root:
            completion_id = self.latest_completion.completion_id
            
        self.root.append(CompletionUsage.from_pricing_info(
            completion_id=completion_id,
            prompt_tokens=prompt_tokens,
            cached_tokens=cached_tokens,
            cache_write_tokens=cache_write_tokens,
            response_tokens=response_tokens,
            pricing=self.pricing
        ))

    @computed_field
    def pricing(self) -> Optional[PricingConfig]:
        """Returns the current pricing configuration."""
        return self._pricing
    
    @pricing.setter
    def pricing(self, pricing_info: PricingConfig):
        """Sets the pricing configuration."""
        self._pricing = pricing_info

    def set_pricing(self, input_1m: float, output_1m: float):
        """Sets basic pricing rates (per 1M tokens)."""
        self._pricing = PricingConfig(
            input=input_1m,
            output=output_1m
        )

    @computed_field
    def latest_completion(self) -> Union[None, CompletionUsage]:
        """Returns the most recent completion."""
        return self.completions[-1] if self.root else None
    
    def _is_aggregated(self) -> bool:
        """Checks if completions are already aggregated by completion_id."""
        completion_ids = [item.completion_id for item in self.root]
        return len(completion_ids) == len(set(completion_ids))

    @computed_field
    def completions(self) -> List[CompletionUsage]:
        """Returns aggregated completions by completion_id."""
        if self._is_aggregated():
            return self.root
        
        aggregated = defaultdict(lambda: {"prompt_tokens": 0, "response_tokens": 0, "cached_tokens": 0, "cache_write_tokens": 0})
        unique_items = []
        seen_ids = set()
        items_to_aggregate = []
        
        for item in self.root:
            comp_id = item.completion_id
            if comp_id in seen_ids:
                items_to_aggregate.append(item)
            else:
                seen_ids.add(comp_id)
                unique_items.append(item)
        
        for item in items_to_aggregate:
            comp_id = item.completion_id
            aggregated[comp_id]["prompt_tokens"] += item.prompt_tokens
            aggregated[comp_id]["response_tokens"] += item.response_tokens
            aggregated[comp_id]["cached_tokens"] += item.cached_tokens
            aggregated[comp_id]["cache_write_tokens"] += item.cache_write_tokens
        
        result = unique_items.copy()
        for comp_id, tokens in aggregated.items():
            for i, item in enumerate(result):
                if item.completion_id == comp_id:
                    if item.completion_id is None:
                        result[i] = CompletionUsage.from_pricing_info(
                            completion_id=comp_id,
                            prompt_tokens=tokens["prompt_tokens"],
                            response_tokens=tokens["response_tokens"],
                            cached_tokens=tokens["cached_tokens"],
                            cache_write_tokens=tokens["cache_write_tokens"],
                            pricing=self.pricing
                        )
                    else:
                        result[i] = CompletionUsage.from_pricing_info(
                            completion_id=comp_id,
                            prompt_tokens=item.prompt_tokens + tokens["prompt_tokens"],
                            response_tokens=item.response_tokens + tokens["response_tokens"],
                            cached_tokens=item.cached_tokens + tokens["cached_tokens"],
                            cache_write_tokens=item.cache_write_tokens + tokens["cache_write_tokens"],
                            pricing=self.pricing
                        )
                    break
        self.root = result
        return result
    
    @computed_field
    def total_tokens(self) -> int:
        """Returns the total number of tokens across all completions."""
        return sum(completion.total_tokens for completion in self.completions)
    
    @computed_field
    def total_cost(self) -> float:
        """Returns the total cost across all completions."""
        return sum(completion.cost for completion in self.completions)
    
    def __str__(self) -> str:
        """Returns a human-readable string representation of the total usage."""
        cost_prefix = f"Cost: ${self.total_cost} | " if self.total_cost else ""
        return f"Total |{cost_prefix} Tokens: {self.total_tokens}"
