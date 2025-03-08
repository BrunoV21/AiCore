from aicore.llm.pricing import PricingConfig

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
        kwargs = {
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens
        }
        if completion_id is not None:
            kwargs["completion_id"] = completion_id
        
        self.root.append(CompletionUsage(**kwargs))

    @computed_field
    def pricing(self)->PricingConfig:
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

    @computed_field
    def completions(self)->List[CompletionUsage]:
        # Use defaultdict to accumulate values for each completion_id
        aggregated = defaultdict(lambda: {"prompt_tokens": 0, "response_tokens": 0})
        
        # Aggregate token counts by completion_id
        for item in self.root:
            comp_id = item.completion_id
            aggregated[comp_id]["prompt_tokens"] += item.prompt_tokens
            aggregated[comp_id]["response_tokens"] += item.response_tokens
        
        # Convert back to CompletionUsage objects
        result = []
        for comp_id, tokens in aggregated.items():
            if self.pricing is not None:
                cost = self.pricing.input * tokens["prompt_tokens"] \
                     + self.pricing.output * tokens["response_tokens"]
                cost *= 1e-6
            else:
                cost = 0
            
            result.append(
                CompletionUsage(
                    completion_id=comp_id,
                    prompt_tokens=tokens["prompt_tokens"],
                    response_tokens=tokens["response_tokens"],
                    cost=cost
                )
            )

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
