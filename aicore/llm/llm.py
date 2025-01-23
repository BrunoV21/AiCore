from pydantic import BaseModel, RootModel, model_validator
from typing import Self, List, Union, Dict, List, Optional
from pathlib import Path
from enum import Enum

from aicore.llm.config import LlmConfig
from aicore.llm.providers import BaseProvider, OpenAiLlm, MistralLlm, GroqLlm, GeminiLlm

class Providers(Enum):
    OPENAI = OpenAiLlm
    MISTRAL = MistralLlm
    GROQ = GroqLlm
    GEMINI = GeminiLlm

    def get_instance(self, config: LlmConfig) -> BaseProvider:
        """
        Instantiate the provider associated with the enum.
        
        Args:
            config (EmbeddingsConfig): Configuration for the provider.
        
        Returns:
            BaseProvider: An instance of the embedding provider.
        """
        return self.value.from_config(config)

class Llm(BaseModel):
    config :LlmConfig
    _provider :BaseProvider=None
    
    @property
    def provider(self)->BaseProvider:
        return self._provider
    
    @provider.setter
    def provider(self, provider :BaseProvider):
        self._provider = provider
    
    @model_validator(mode="after")
    def start_provider(self)->Self:
        self._provider = Providers[self.config.provider.upper()].get_instance(self.config)
        return self
    
    @classmethod
    def from_config(cls, config :LlmConfig)->"Llm":
        return cls(config=config)
    
    @property
    def tokenizer(self):
        return self.provider.tokenizer_fn
    
    def complete(self,
                 prompt :Union[str, BaseModel, RootModel], 
                 system_prompt :Optional[str]=None,
                 prefix_prompt :Optional[str]=None,
                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                 json_output :bool=False,
                 stream :bool=True)->Union[str, Dict]:
        
        return self.provider.complete(prompt, system_prompt, prefix_prompt, img_path, json_output, stream)
    
    async def acomplete(self,
                 prompt :Union[str, BaseModel, RootModel],
                 system_prompt :Optional[str]=None,
                 prefix_prompt :Optional[str]=None,
                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                 json_output :bool=False,
                 stream :bool=True)->Union[str, Dict]:
         
         return await self.provider.acomplete(prompt, system_prompt, prefix_prompt, img_path, json_output, stream)

if __name__ == "__main__":
    import asyncio
    from aicore.config import config

    async def main():
        llm_obj = Llm.from_config(config.llm)
        print("Sync reponse:")
        llm_obj.complete("When are going to Mars with Elon Musk?")
        print("\nAsync response:")
        await llm_obj.acomplete("When are going to Mars with Elon Musk?")

    asyncio.run(main())
