from aicore.embeddings.providers.base_provider import BaseProvider
from pydantic import model_validator
from openai import OpenAI, AsyncOpenAI
from openai.types.create_embedding_response import CreateEmbeddingResponse
from typing import List, Self

class OpenAiEmbeddings(BaseProvider):
    vector_dimensions :int=1536

    @model_validator(mode="after")
    def set_openai(self)->Self:

        self.client :OpenAI = OpenAI(
            api_key=self.config.api_key
        )

        self.aclient :AsyncOpenAI = AsyncOpenAI(
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