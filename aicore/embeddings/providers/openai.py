from aicore.embeddings.providers.base_provider import EmbeddingsBaseProvider
from pydantic import model_validator
from openai import OpenAI, AsyncOpenAI
from openai.types.create_embedding_response import CreateEmbeddingResponse
from typing import Optional, List, Self

class OpenAiEmbeddings(EmbeddingsBaseProvider):
    vector_dimensions :int=1536
    base_url :Optional[str]=None

    @model_validator(mode="after")
    def set_openai(self)->Self:

        self.client :OpenAI = OpenAI(
            api_key=self.config.api_key,
            base_url=self.base_url
        )

        self.aclient :AsyncOpenAI = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.base_url
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