from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.logger import default_stream_handler
from aicore.const import STREAM_START_TOKEN, STREAM_END_TOKEN, REASONING_STOP_TOKEN
from pydantic import model_validator
# from mistral_common.protocol.instruct.messages import UserMessage
# from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
from mistralai import Mistral, CompletionEvent, CompletionResponseStreamChoice, models
from typing import Self, Optional, Union, List, Literal, Dict
import tiktoken

#TODO replace Tiktoken with Mistral tekken encoder when it is updated to work on python 3.13#
class MistralLlm(LlmBaseProvider):

    @model_validator(mode="after")
    def set_mistral(self)->Self:

        self.client :Mistral = Mistral(
            api_key=self.config.api_key
        )
        self.validate_config(models.SDKError)
        ### Suspect Misral will always stream by default
        self.completion_fn = self.client.chat.stream
        self.acompletion_fn = self.client.chat.stream_async
        self.normalize_fn = self.normalize
        self.tokenizer_fn = tiktoken.encoding_for_model(
            self.get_default_tokenizer(
                self.config.model
            )
        ).encode

        return self
    
    def normalize(self, chunk:CompletionEvent, completion_id :Optional[str]=None)->CompletionResponseStreamChoice:
        data = chunk.data
        if data.usage is not None:
            self.usage.record_completion(
                prompt_tokens=data.usage.prompt_tokens,
                response_tokens=data.usage.completion_tokens,
                completion_id=completion_id or data.id
            )
        return data.choices
    
    def _message_body(self, prompt: Union[List[str], str], role: Literal["user", "system", "assistant"] = "user", img_b64_str: Optional[List[str]] = None, _last: Optional[bool] = False) -> Dict:
        message_body = {
            "role": role,
            "content": self._message_content(prompt, img_b64_str)
        }
        if role == "assistant" and _last:
            message_body["prefix"] = True
        return message_body
    
    def _stream(self, stream, prefix_prompt :Optional[Union[str, List[str]]]=None)->str:
        message = []

        prefix_prompt = "".join(prefix_prompt) if isinstance(prefix_prompt, list) else prefix_prompt
        prefix_buffer = []
        prefix_completed = not bool(prefix_prompt)
        for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                if prefix_completed:
                    default_stream_handler(chunk_message)
                    message.append(chunk_message)
                else:
                    prefix_buffer.append(chunk_message)
                    if "".join(prefix_buffer) == prefix_prompt:
                        prefix_completed = True
                
        if self._is_reasoner:
            default_stream_handler(REASONING_STOP_TOKEN)
        response = "".join(message)
        return response
    
    async def _astream(self, stream, logger_fn, prefix_prompt :Optional[Union[str, List[str]]]=None)->str:
        message = []
    
        await logger_fn(STREAM_START_TOKEN) if not prefix_prompt else ...
        prefix_prompt = "".join(prefix_prompt) if isinstance(prefix_prompt, list) else prefix_prompt
        prefix_buffer = []
        prefix_completed = not bool(prefix_prompt)
        async for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                if prefix_completed:
                    await logger_fn(chunk_message)
                    message.append(chunk_message)
                else:
                    prefix_buffer.append(chunk_message)
                    if "".join(prefix_buffer) == prefix_prompt:
                        prefix_completed = True
                        await logger_fn(STREAM_START_TOKEN)
        
        if self._is_reasoner:
            await logger_fn(REASONING_STOP_TOKEN)
        else:
            await logger_fn(STREAM_END_TOKEN)
        response = "".join(message)
        return response