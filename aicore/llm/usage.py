from aicore.pricing import PricingConfig

from pydantic import BaseModel, RootModel, Field, computed_field
from typing import Optional, List, Union
from collections import defaultdict
from ulid import ulid

class CompletionUsage(BaseModel):
    completion_id :Optional[str]=Field(default_factory=ulid)
    prompt_tokens :int
    response_tokens :int
    cost :Optional[float]=0

    @property
    def input_tokens(self)->int:
        return self.prompt_tokens
    
    @property
    def output_tokens(self)->int:
        return self.response_tokens
    
    @computed_field
    def total_tokens(self)->int:
        return self.input_tokens + self.output_tokens
    
    def __str__(self)->str:
        cost_prefix = f"Cost: ${self.cost} | " if self.cost else ""
        return f"{cost_prefix}Tokens: {self.total_tokens} | Prompt: {self.prompt_tokens} | Response: {self.response_tokens}"
    
    @classmethod
    def from_pricing_info(cls,
        completion_id :str,
        prompt_tokens :int,
        response_tokens :int,
        cost :Optional[float]=0,
        pricing :Optional[PricingConfig]=None)->"CompletionUsage":
        if pricing is not None:
            cost = pricing.input * prompt_tokens + pricing.output * response_tokens
            cost *= 1e-6
        return cls(
            completion_id=completion_id,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            cost=cost,
        )
    
    def update_with_pricing(self, pricing :PricingConfig):
        if not self.cost:
            self.cost = pricing.input * self.prompt_tokens + pricing.output * self.response_tokens

class UsageInfo(RootModel):
    root :List[CompletionUsage]=[]
    _pricing :Optional[PricingConfig]=None

    @classmethod
    def from_pricing_config(cls, pricing :PricingConfig)->"UsageInfo":
        cls = cls()
        cls.pricing = pricing
        return cls

    def record_completion(self,
                prompt_tokens :int,
                response_tokens :int,
                completion_id :Optional[str]=None
        ):
        if completion_id is None and self.root:
            completion_id = self.latest_completion.completion_id
        self.root.append(CompletionUsage.from_pricing_info(
            completion_id=completion_id,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            pricing=self.pricing
        ))

    @computed_field
    def pricing(self)->Optional[PricingConfig]:
        return self._pricing
    
    @pricing.setter
    def pricing(self, pricing_info :PricingConfig):
        self._pricing = pricing_info

    def set_pricing(self, input_1m :float, output_1m :float):
        self._pricing = PricingConfig(
            input=input_1m,
            output=output_1m
        )

    @computed_field
    def latest_completion(self)->Union[None, CompletionUsage]:
        return self.completions[-1] if self.root else None
    
    def _is_aggregated(self) -> bool:
        """
        Check if the self.root already contains only unique completion_ids.
        
        Returns:
            bool: True if no completion_id is repeated, False otherwise.
        """
        # Extract all completion_ids
        completion_ids = [item.completion_id for item in self.root]
        
        # If there are no items or all items have unique IDs, it's already aggregated
        return len(completion_ids) == len(set(completion_ids))

    @computed_field
    def completions(self) -> List[CompletionUsage]:
        # If already aggregated, just return the current root
        if self._is_aggregated():
            return self.root
        
        # Use defaultdict to accumulate values for each completion_id
        aggregated = defaultdict(lambda: {"prompt_tokens": 0, "response_tokens": 0})
        
        # Collect unique items (those with unique completion_ids)
        unique_items = []
        seen_ids = set()
        items_to_aggregate = []
        
        # Separate items into unique and to-be-aggregated
        for item in self.root:
            comp_id = item.completion_id
            if comp_id in seen_ids:
                items_to_aggregate.append(item)
            else:
                seen_ids.add(comp_id)
                unique_items.append(item)
        
        # Aggregate only the repeated IDs
        for item in items_to_aggregate:
            comp_id = item.completion_id
            aggregated[comp_id]["prompt_tokens"] += item.prompt_tokens
            aggregated[comp_id]["response_tokens"] += item.response_tokens
        
        # Update the existing items with aggregated values
        result = unique_items.copy()
        for comp_id, tokens in aggregated.items():
            # Find the existing item with this ID
            for i, item in enumerate(result):
                if item.completion_id == comp_id:
                    # Update token counts
                    prompt_tokens = item.prompt_tokens + tokens["prompt_tokens"]
                    response_tokens = item.response_tokens + tokens["response_tokens"]                    
                    # Replace with updated item
                    result[i] = CompletionUsage.from_pricing_info(
                        completion_id=comp_id,
                        prompt_tokens=prompt_tokens,
                        response_tokens=response_tokens,
                        pricing=self.pricing
                    )
                    break
        
        self.root = result
        return result
    
    @computed_field
    def total_tokens(self)->int:
        return sum([completion.total_tokens for completion in self.completions])
    
    @computed_field
    def total_cost(self)->float:
        return sum([completion.cost for completion in self.completions])
    
    def __str__(self)->str:
        cost_prefix = f"Cost: ${self.total_cost} | " if self.total_cost else ""
        return f"Total |{cost_prefix} Tokens: {self.total_tokens}"
