from aicore.embeddings.providers.base_provider import EmbeddingsBaseProvider
from pydantic import model_validator
from groq import Groq, AsyncGroq
from groq.types import CreateEmbeddingResponse
from typing import List
from typing_extensions import Self

class GroqEmbeddings(EmbeddingsBaseProvider):
    vector_dimensions :int=1024

    @model_validator(mode="after")
    def set_groq(self)->Self:

        self.client :Groq = Groq(
            api_key=self.config.api_key
        )

        self.aclient :AsyncGroq = AsyncGroq(
            api_key=self.config.api_key
        )

        return self
    
    def generate(self, text_batches :List[str])->CreateEmbeddingResponse:
        vectors = self.client.embeddings.create(
            model=self.config.model,
            input=text_batches
        )

        #TODO create base embedding basemodel to map from Mistral EmbeddingResponse

        return vectors
    
    async def agenerate(self, text_batches :List[str])->CreateEmbeddingResponse:
        vectors = self.aclient.embeddings.create(
            model=self.config.model,
            input=text_batches
        )

        return vectors