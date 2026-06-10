from aicore.llm.providers.openai import OpenAiLlm
from typing_extensions import Self
from pydantic import model_validator

class GrokLlm(OpenAiLlm):
    
    base_url :str="https://api.x.ai/v1"
    _skip_model_valiation :bool=True

    @model_validator(mode="after")
    def post_validate(self)->Self:
        self.validate_config(force=True)
        return self
