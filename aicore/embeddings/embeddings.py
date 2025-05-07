from pydantic import BaseModel, model_validator
from typing import List
from typing_extensions import Self
from enum import Enum

from aicore.utils import retry_on_failure
from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings.providers import (
    EmbeddingsBaseProvider,
    OpenAiEmbeddings,
    MistralEmbeddings,
    NvidiaEmbeddings,
    GroqEmbeddings,
    GeminiEmbeddings
)

class Providers(Enum):
    OPENAI :OpenAiEmbeddings=OpenAiEmbeddings
    NVIDIA :NvidiaEmbeddings=NvidiaEmbeddings
    MISTRAL :MistralEmbeddings=MistralEmbeddings
    GROQ :GroqEmbeddings=GroqEmbeddings
    GEMINI :GeminiEmbeddings=GeminiEmbeddings

    def get_instance(self, config: EmbeddingsConfig) -> EmbeddingsBaseProvider:
        """
        Instantiate the provider associated with the enum.
        
        Args:
            config (EmbeddingsConfig): Configuration for the provider.
        
        Returns:
            EmbeddingsBaseProvider: An instance of the embedding provider.
        """
        return self.value.from_config(config)

class Embeddings(BaseModel):
    config :EmbeddingsConfig
    _provider :EmbeddingsBaseProvider=None
    
    @property
    def provider(self)->EmbeddingsBaseProvider:
        return self._provider
    
    @provider.setter
    def provider(self, provider :EmbeddingsBaseProvider):
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
    
    @retry_on_failure
    def generate(self, text_batches :List[str]):
        return self.provider.generate(text_batches)
    
    @retry_on_failure
    async def agenerate(self, text_batches :List[str]):
        ### Carefull wtih async to avoid getting ratelimited
        return await self.provider.agenerate(text_batches)

if __name__ == "__main__":

    import asyncio    
    from aicore.config import Config
    from aicore.embeddings.providers.mistral import EmbeddingResponseData, EmbeddingResponse

    # print(Embeddings.from_config(config.embeddings).generate(["Hi there, how you doing mate?"]))

    async def main():
        config = Config.from_yaml()
        embeddings_obj = Embeddings.from_config(config.embeddings)
        print(embeddings_obj.vector_dimensions)
        vectors = await embeddings_obj.agenerate(["Hi there, how you doing mate?"])
        # print(vectors)
        print(len(vectors.data[0].embedding))

    asyncio.run(main())