from aicore.llm.config import LlmConfig
from aicore.llm.utils import parse_content, image_to_base64
from typing import Any, Dict, Self, Optional, Literal, List, Union
from pydantic import BaseModel, RootModel
from pathlib import Path
import tiktoken
import json

#TODO keep track of usage in accordance to embeddings tracking model
class BaseProvider(BaseModel):
    config :LlmConfig
    _client :Any=None
    _aclient :Any=None
    _completion_args :Dict=None
    _completion_fn :Any=None
    _acompletion_fn :Any=None
    _normalize_fn :Any=None
    _tokenizer_fn :Any=None

    @classmethod
    def from_config(cls, config :LlmConfig)->"BaseProvider":
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

    @property
    def completion_args(self)->Dict:
        return self._completion_args
    
    @completion_args.setter
    def completion_args(self, args :Dict):
        self._completion_args = args

    @property
    def completion_fn(self)->Any:
        return self._completion_fn
    
    @completion_fn.setter
    def completion_fn(self, completion_fn :Any):
        self._completion_fn = completion_fn

    @property
    def acompletion_fn(self)->Any:
        return self._acompletion_fn
    
    @acompletion_fn.setter
    def acompletion_fn(self, acompletion_fn :Any):
        self._acompletion_fn = acompletion_fn

    @property
    def normalize_fn(self)->Any:
        return self._normalize_fn
    
    @normalize_fn.setter
    def normalize_fn(self, normalize_fn :Any):
        self._normalize_fn = normalize_fn

    @property
    def tokenizer_fn(self)->Any:
        return self._tokenizer_fn
    
    @tokenizer_fn.setter
    def tokenizer_fn(self, tokenizer_fn :Any):
        self._tokenizer_fn = tokenizer_fn    

    @staticmethod
    def get_default_tokenizer(model_name :str)->str:
        try:
            return tiktoken.encoding_name_for_model(model_name)
        except KeyError:
            return "gpt-4o"

    @staticmethod
    def _message_content(prompt :str, img_b64_str :Optional[List[str]]=None)->List[Dict]:
        message_content = [
            {
                "type": "text",
                "text": prompt
            } 
        ]
        if img_b64_str is not None:
            for img in img_b64_str:
                message_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}"},
                    }
                )
        return message_content

    def _message_body(self, prompt :str, role :Literal["user", "system", "assistant"]="user", img_b64_str :Optional[List[str]]=None)->Dict:
        message_body = {
            "role": role,
            "content": self._message_content(prompt, img_b64_str)
        }
        if role == "assistant" and self.config.provider == "mistral":
            message_body["prefix"] = True
        return message_body

    def completion_args_template(self, prompt :str, system_prompt :Optional[str]=None, prefix_prompt :Optional[str]=None, img_b64_str :Optional[Union[str, List[str]]]=None, stream :bool=False)->Dict:
        if img_b64_str and isinstance(img_b64_str, str):
            img_b64_str = [img_b64_str]

        messages = []
        if system_prompt is not None:
            messages.append(self._message_body(system_prompt, role="system"))
        messages.append(self._message_body(prompt, role="user"))
        if prefix_prompt is not None:
            messages.append(self._message_body(prefix_prompt, role="assistant"))
        
        args = dict(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            messages=messages,
            stream=stream
        )

        if self.completion_args:
            args.update(self.completion_args)
        
        return args
    
    def _prepare_completion_args(self,
                                 prompt :str, 
                                 system_prompt :Optional[str]=None,
                                 prefix_prompt :Optional[str]=None,
                                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                                 stream :bool=True)->Dict:
        if img_path and not isinstance(img_path, list):
            img_path = [img_path]

        img_b64_str = [
            image_to_base64(img)
            for img in img_path
        ] if img_path else None

        completion_args = self.completion_args_template(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_b64_str=img_b64_str,
            stream=stream
        )

        return completion_args
    
    def _stream(self, stream)->str:
        message = []
        for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                print(chunk_message, end="")
                message.append(chunk_message)
        # usage = chunk.usage if self.provider == "openai" else None
        # Combine the streamed message into a single response
        response = "".join(message)
        return response
    
    async def _astream(self, stream)->str:
        message = []
        async for chunk in stream:
            _chunk = self.normalize_fn(chunk)
            if _chunk:
                chunk_message = _chunk[0].delta.content or ""
                print(chunk_message, end="")
                message.append(chunk_message)
        # usage = chunk.usage if self.provider == "openai" else None
        # Combine the streamed message into a single response
        response = "".join(message)
        return response
    
    @staticmethod
    def model_to_str(model :Union[BaseModel, RootModel])->str:
        return f"```json\n{model.model_dump_json(indent=4)}\n```"
    
    @staticmethod
    def extract_json(output :str)->Dict:
        return json.loads(parse_content(output))

    def complete(self,
                 prompt :Union[str, BaseModel, RootModel], 
                 system_prompt :Optional[str]=None,
                 prefix_prompt :Optional[str]=None,
                 img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                 json_output :bool=False,
                 stream :bool=True)->Union[str, Dict]:
        
        if isinstance(prompt, Union[BaseModel, RootModel]):
            prompt = self.model_to_str(prompt)
        
        completion_args = self._prepare_completion_args(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_path=img_path,
            stream=stream
        )
        output = self.completion_fn(**completion_args)

        if stream:
            output = self._stream(output)

        return output if not json_output else self.extract_json(output)

    async def acomplete(self,
                        prompt :Union[str, BaseModel, RootModel], 
                        system_prompt :Optional[str]=None,
                        prefix_prompt :Optional[str]=None,
                        img_path :Optional[Union[Union[str, Path], List[Union[str, Path]]]]=None,
                        json_output :bool=False,
                        stream :bool=True)->Union[str, Dict]:
        
        if isinstance(prompt, Union[BaseModel, RootModel]):
            prompt = self.model_to_str(prompt)
        
        completion_args = self._prepare_completion_args(
            prompt=prompt,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            img_path=img_path,
            stream=stream
        )
        output = await self.acompletion_fn(**completion_args)

        if stream:
            output = await self._astream(output)

        return output if not json_output else self.extract_json(output)