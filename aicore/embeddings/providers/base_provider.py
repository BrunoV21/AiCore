from aicore.embeddings.config import EmbeddingsConfig

from pydantic import BaseModel
from typing import Any

class EmbeddingsBaseProvider(BaseModel):
    config :EmbeddingsConfig
    vector_dimensions :int
    _client :Any=None
    _aclient :Any=None

    @classmethod
    def from_config(cls, config :EmbeddingsConfig)->"EmbeddingsBaseProvider":
        return cls(
            config=config
        )
    
    @property
    def client(self):
        return self._client
    
    @client.setter
    def client(self, client :Any):
        self._client = client

    @property
    def aclient(self):
        return self._aclient
    
    @client.setter
    def aclient(self, aclient :Any):
        self._aclient = aclient

    def generate(self):
        ...

    async def agenerate(self):
        ...