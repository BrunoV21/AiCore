from aicore.llm.providers.openai import OpenAiLlm
from pydantic import model_validator
from typing_extensions import Self

class ZaiLlm(OpenAiLlm):
    
    base_url :str="https://api.z.ai/api/paas/v4/"

    @model_validator(mode="after")
    def post_validate(self)->Self:
        self.validate_config(force=True)
