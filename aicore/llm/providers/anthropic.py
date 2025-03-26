from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.models import AuthenticationError
from aicore.logger import default_stream_handler
from pydantic import model_validator
from typing import Self, Optional, Dict, Union, List
from anthropic import Anthropic, AsyncAnthropic, AuthenticationError
from functools import partial

class AnthropicLlm(LlmBaseProvider):

    @staticmethod
    def anthropic_count_tokens(contents :str, client :AsyncAnthropic, model :str):
        """
        unfortunately system messages can not be included into the count's default method
        due to the way the tokennizer fn has been implemented in aicore
        """
        response = client.messages.count_tokens(
            model=model,
            messages=[{
                "role": "user",
                "content": contents
            }],
        )
        input_tokens = response.model_dump().get("input_tokens")
        return [i for i in range(input_tokens)] if input_tokens else []

    @model_validator(mode="after")
    def set_anthropic(self)->Self:
        _client :Anthropic = Anthropic(
            api_key=self.config.api_key
        )
        self.client :Anthropic = _client
        self.validate_config(AuthenticationError)
        _aclient :AsyncAnthropic = AsyncAnthropic(
            api_key=self.config.api_key
        )
        self._aclient = _aclient
        self.completion_fn = _client.messages.create
        self.acompletion_fn = _aclient.messages.create
        self.normalize_fn = self.normalize

        self.tokenizer_fn = partial(
            self.anthropic_count_tokens,
            client=_client,
            model=self.config.model
        )

        self._handle_thinking_models()

        return self

    def normalize(self, event, completion_id :Optional[str]=None):
        """  async for event in stream:
            event_type = event.type
            if event_type == "message_start":
                usage.input_tokens = event.message.usage.input_tokens
                usage.output_tokens = event.message.usage.output_tokens
            elif event_type == "content_block_delta":
                content = event.delta.text
                log_llm_stream(content)
                collected_content.append(content)
            elif event_type == "message_delta":
                usage.output_tokens = event.usage.output_tokens  # update final output_tokens
        """
        event_type = event.type
        input_tokens = 0
        output_tokens = 0
        if event_type == "message_start":
            input_tokens = event.message.usage.input_tokens
            output_tokens = event.message.usage.output_tokens
            self.usage.record_completion(
                prompt_tokens=input_tokens,
                response_tokens=output_tokens,
                completion_id=completion_id or event.message.id
            )
        elif event_type == "content_block_delta":
            return event
        elif event_type == "message_delta":
            output_tokens = event.usage.output_tokens
            self.usage.record_completion(
                prompt_tokens=input_tokens,
                response_tokens=output_tokens,
                completion_id=completion_id
            )

    @staticmethod
    def _handle_stream_messages(event, message)->list:
        delta = event.delta
        chunk_message = getattr(delta, "text", "")
        chunk_thinking = getattr(delta, "thinking", None)
        chunk_signature = getattr(delta, "signature", None)
        chunk_stream = chunk_message or chunk_thinking or chunk_signature
        default_stream_handler(chunk_stream)
        if chunk_message:
            message.append(chunk_message)
    
    @staticmethod
    async def _handle_astream_messages(event, logger_fn, message)->list:
        delta = event.delta
        chunk_message = getattr(delta, "text", "")
        chunk_thinking = getattr(delta, "thinking", None)
        chunk_signature = getattr(delta, "signature", None)
        chunk_stream = chunk_message or chunk_thinking or chunk_signature
        await logger_fn(chunk_stream)
        if chunk_message:
            message.append(chunk_message)

    def _handle_system_prompt(self,
            messages :list,
            system_prompt: Optional[Union[List[str], str]] = None):                
        pass

    @staticmethod
    def _handle_special_sys_prompt_anthropic(args :Dict, system_prompt: Optional[Union[List[str], str]] = None):
        if system_prompt:
            args["system"] = "\n".join(system_prompt) if isinstance(system_prompt, list) else system_prompt

    def _handle_thinking_models(self):
        thinking = getattr(self.config, "thinking", None)
        if thinking:
            if isinstance(thinking, bool):
                self.completion_args["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.config.max_tokens
                }
            elif isinstance(thinking, dict):
                self.completion_args["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": thinking.get("budget_tokens") or self.config.max_tokens
                }