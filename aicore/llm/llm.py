from pydantic import BaseModel, RootModel, model_validator
from typing import Self, List, Union, Dict, List, Optional
from pathlib import Path
from enum import Enum

from aicore.llm.config import LlmConfig
from aicore.llm.providers import (
    LlmBaseProvider,
    OpenAiLlm,
    MistralLlm, 
    NvidiaLlm,
    GroqLlm,
    GeminiLlm
)

class Providers(Enum):
    OPENAI = OpenAiLlm
    MISTRAL = MistralLlm
    NVIDIA = NvidiaLlm
    GROQ = GroqLlm
    GEMINI = GeminiLlm

    def get_instance(self, config: LlmConfig) -> LlmBaseProvider:
        """
        Instantiate the provider associated with the enum.
        
        Args:
            config (EmbeddingsConfig): Configuration for the provider.
        
        Returns:
            LlmBaseProvider: An instance of the embedding provider.
        """
        return self.value.from_config(config)

class Llm(BaseModel):
    config :LlmConfig
    _provider :Union[LlmBaseProvider, None]=None
    _reasoner :Union["Llm", None]=None
    
    @property
    def provider(self)->LlmBaseProvider:
        return self._provider
    
    @provider.setter
    def provider(self, provider :LlmBaseProvider):
        self._provider = provider

    @property
    def reasoner(self)->"Llm":
        return self._reasoner
    
    @reasoner.setter
    def reasoner(self, reasoning_llm :"Llm"):
        self._reasoner = reasoning_llm
    
    @model_validator(mode="after")
    def start_provider(self)->Self:
        self.provider = Providers[self.config.provider.upper()].get_instance(self.config)
        self.reasoner = Llm.from_config(self.config.reasoner) if self.config.reasoner else None
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
