from aicore.embeddings.providers.base_provider import EmbeddingsBaseProvider
from pydantic import model_validator
from mistralai import Mistral, EmbeddingResponse, EmbeddingResponseData
from typing import List
from typing_extensions import Self

class MistralEmbeddings(EmbeddingsBaseProvider):
    vector_dimensions :int=1024

    @model_validator(mode="after")
    def set_mistral(self)->Self:

        self.client :Mistral = Mistral(
            api_key=self.config.api_key
        )

        return self
    
    def generate(self, text_batches :List[str])->EmbeddingResponse:
        vectors = self.client.embeddings.create(
            model=self.config.model,
            inputs=text_batches
        )

        #TODO create base embedding basemodel to map from Mistral EmbeddingResponse

        return vectors
    
    async def agenerate(self, text_batches :List[str])->EmbeddingResponse:
        vectors = await self.client.embeddings.create_async(
            model=self.config.model,
            inputs=text_batches
        )

        return vectors