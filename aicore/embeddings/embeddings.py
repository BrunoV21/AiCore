from pydantic import BaseModel, model_validator
from typing import Self, List
from enum import Enum

from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings.providers import BaseProvider, OpenAiEmbeddings, MistralEmbeddings

class Providers(Enum):
    OPENAI = OpenAiEmbeddings
    MISTRAL = MistralEmbeddings

    def get_instance(self, config: EmbeddingsConfig) -> BaseProvider:
        """
        Instantiate the provider associated with the enum.
        
        Args:
            config (EmbeddingsConfig): Configuration for the provider.
        
        Returns:
            BaseProvider: An instance of the embedding provider.
        """
        return self.value.from_config(config)

class Embeddings(BaseModel):
    config :EmbeddingsConfig
    _provider :BaseProvider=None
    
    @property
    def provider(self)->BaseProvider:
        return self._provider
    
    @provider.setter
    def provider(self, provider :BaseProvider):
        self._provider = provider
    
    @property
    def vector_dimensions(self)->int:
        return self.provider.vector_dimensions
    
    @model_validator(mode="after")
    def start_provider(self)->Self:
        self.provider = Providers[self.config.provider.upper()].get_instance(self.config)
        return self
    
    @classmethod
    def from_config(cls, config :EmbeddingsConfig)->"Embeddings":
        return cls(config=config)
    
    def generate(self, text_batches :List[str]):
        return self.provider.generate(text_batches)
    
    async def agenerate(self, text_batches :List[str]):
        ### Carefull wtih async to avoid getting ratelimited
        return await self.provider.agenerate(text_batches)

if __name__ == "__main__":

    import asyncio    
    from aicore.config import config
    from aicore.embeddings.providers.mistral import EmbeddingResponseData, EmbeddingResponse

    # print(Embeddings.from_config(config.embeddings).generate(["Hi there, how you doing mate?"]))

    async def main():
        embeddings_obj = Embeddings.from_config(config.embeddings)
        print(embeddings_obj.vector_dimensions)
        vectors = await embeddings_obj.agenerate(["Hi there, how you doing mate?"])
        # print(vectors)
        print(len(vectors.data[0].embedding))

    asyncio.run(main())