from aicore.llm.providers.openai import OpenAiLlm
from aicore.llm.mcp.models import ToolCallSchema
from pydantic import model_validator
from google.genai import Client
from functools import partial
from openai.types.chat import ChatCompletion
from typing import List, Optional, Any
from typing_extensions import Self

class GeminiLlm(OpenAiLlm):
    base_url :str="https://generativelanguage.googleapis.com/v1beta/openai/"
    _current_signature :Optional[Any]=None

    @staticmethod
    def gemini_count_tokens(contents :str, client :Client, model :str)->List[int]:
        response = client.models.count_tokens(
            contents=contents,
            model=model
        )
        return [i for i in range(response.total_tokens)] if response.total_tokens else []

    @model_validator(mode="after")
    def pass_gemini_tokenizer_fn(self)->Self:
        _client = Client(
            api_key=self.config.api_key
        )
        self.tokenizer_fn = partial(
            self.gemini_count_tokens,
            client=_client,
            model=self.config.model
        )

        return self

    def normalize(self, chunk :ChatCompletion, completion_id :Optional[str]=None):
        usage = chunk.usage
        if usage is not None and usage.completion_tokens:
            return super().normalize(chunk, completion_id)
        return chunk.choices
    
    def _fill_tool_schema(self, tool_chunk)->ToolCallSchema:
        tool_call = ToolCallSchema(
            id=tool_chunk.id,
            name=tool_chunk.function.name,
            arguments=tool_chunk.function.arguments
        )
        tool_call._raw = tool_chunk.function
        if extra_content := getattr(tool_chunk, "extra_content", None):
            tool_call.extra_content = extra_content
            self._current_signature = tool_call.extra_content
        elif self._current_signature is not None:
            tool_call.extra_content = self._current_signature

        return tool_call

    def _to_provider_tool_call_schema(self, toolCallSchema :ToolCallSchema)->ToolCallSchema:
        toolCallDict = {
            "id": toolCallSchema.id,
            "function": {
                "name": toolCallSchema.name,
                "arguments": toolCallSchema.arguments_as_string()
            },
            "type": "function"
        }
        if toolCallSchema.extra_content is not None:
            toolCallDict["extra_content"] = toolCallSchema.extra_content

        toolCallSchema._raw = {
            "role": "assistant",
            "tool_calls": [
                toolCallDict
            ]
        }

        return toolCallSchema
