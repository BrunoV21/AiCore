from pydantic import model_validator
from typing_extensions import Self
from aicore.llm.providers.openai import OpenAiLlm

class OpenRouterLlm(OpenAiLlm):
    
    base_url :str="https://openrouter.ai/api/v1"
    _skip_model_valiation :bool=True

    @model_validator(mode="after")
    def post_validate(self)->Self:
        self.validate_config(force=True)
