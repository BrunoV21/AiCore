from aicore.llm.providers.base_provider import BaseProvider
from pydantic import model_validator
# from mistral_common.protocol.instruct.messages import UserMessage
# from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
from mistralai import Mistral
from typing import Self
import tiktoken

#TODO replace Tiktoken with Mistral tekken encoder when it is updated to work on python 3.13#
class MistralLlm(BaseProvider):

    @model_validator(mode="after")
    def set_mistral(self)->Self:

        self.client :Mistral = Mistral(
            api_key=self.config.api_key
        )
        ### Suspect Misral will always stream by default
        self.completion_fn = self.client.chat.stream
        self.acompletion_fn = self.client.chat.stream_async
        self.normalize_fn = self.normalize
        self.tokernizer_fn = tiktoken.get_encoding(
            self.get_default_tokenizer(
                self.config.model
            )
        ).encode

        return self
    
    def normalize(self, chunk):
        return chunk.data.choices