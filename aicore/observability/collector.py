from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE, DEFAULT_ENCODING

from pydantic import BaseModel,  RootModel, Field, field_validator, computed_field
from typing import Dict, Any, Optional, Callable, List, Union, Literal
from datetime import datetime
from pathlib import Path
import ulid
import json
import os

class LlmOperationRecord(BaseModel):
    """Data model for storing information about a single LLM operation."""
    session_id: Optional[str]=None
    operation_id: str = Field(default_factory=ulid.ulid)
    timestamp: str = Field(default_factory=datetime.now().isoformat)
    operation_type: Literal["completion", "acompletion"]
    provider :str
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    cost: Optional[float] = 0
    latency_ms: float
    error_message: Optional[str] = None
    completion_args: Dict[str, Any]
    response: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    @field_validator("response")
    @classmethod
    def json_dumps_response(cls, response :Union[None, str, Dict[str, str]])->Optional[str]:
        if isinstance(response, Union[str, None]):
            return response
        elif isinstance(response, dict):
            return json.dumps(response, indent=4)
        else:
            raise TypeError("response param must be [str] or [json serializable obj]")
    
    @property
    def messages(self)->List[Dict[str, str]]:
        return self.completion_args.get("messages", [])
    
    @computed_field
    def model(self)->str:
        return self.completion_args.get("model")
    
    @computed_field
    def temperature(self)->float:
        return self.completion_args.get("temperature")
    
    @computed_field
    def max_tokens(self)->int:
        return self.completion_args.get("max_tokens")
    
    @computed_field
    def system_prompt(self)->Optional[str]:
        for msg in self.messages:
            if msg.get("role") == "system": #or dev open ai o -series?
                return msg.get("content")
        return None

    @computed_field
    def assistant_message(self)->Optional[str]:
        for msg in self.messages[::-1]:
            if msg.get("role") == "assistant": #or dev open ai o -series?
                return msg.get("content")
        return None

    @computed_field
    def user_prompt(self)->Optional[str]:
        for msg in self.messages[::-1]:
            if msg.get("role") == "user": #or dev open ai o -series?
                return msg.get("content")
        return None
    
    @computed_field
    def history_messages(self)->Optional[str]:
        return json.dumps([
            msg for msg in self.messages
            if msg.get("content") not in [
                self.system_prompt,
                self.assistant_message,
                self.user_prompt
            ]
        ], indent=4)

    @computed_field
    def sucess(self)->bool:
        return bool(self.response)

class LlmOperationCollector(RootModel):
    root :List[LlmOperationRecord] = []
    _storage_path :Optional[Union[str, Path]]=None

    @property
    def storage_path(self)->Optional[Union[str, Path]]:
        return self._storage_path
    
    @storage_path.setter
    def storage_path(self, value :Union[str, Path]):
        self._storage_path = value
    
    def record_completion(
            self,
            completion_args: Dict[str, Any],
            operation_type: Literal["completion", "acompletion"],
            provider :str,
            response: Optional[Union[str, Dict[str, str]]] = None,
            session_id :Optional[str]=None,
            input_tokens: Optional[int]=0,
            output_tokens: Optional[int]=0,
            cost :Optional[float]=0,
            latency_ms: Optional[float] = None, success: bool = True,
            error_message: Optional[str] = None) -> LlmOperationRecord:

        # Clean request args to remove potentially sensitive or large objects
        cleaned_args = self._clean_completion_args(completion_args)
        
        record = LlmOperationRecord(
            session_id=session_id,
            provider=provider,
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms or 0,
            error_message=error_message,
            completion_args=cleaned_args,
            response=response
        )

        if self.storage_path:
            self._store_to_file(record)        
        
        self.root.append(record)
        
        return record

    def _store_to_file(self, new_record :LlmOperationRecord) -> None:
        if not os.path.exists(self.storage_path):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            records = None
        else:
            with open(self.storage_path, 'r', encoding=DEFAULT_ENCODING) as f:
               records = LlmOperationCollector(root=json.loads(f.read()))            
            records.root.append(new_record)
        
        records = records or self

        with open(self.storage_path, 'w', encoding=DEFAULT_ENCODING) as f:
            f.write(records.model_dump_json(indent=4))
    
    @staticmethod
    def _clean_completion_args(args: Dict[str, Any]) -> Dict[str, Any]:
        """Clean request arguments to remove sensitive information."""
        cleaned = args.copy()
        # Remove potentially sensitive information like API keys
        cleaned.pop("api_key", None)
        return cleaned

    @classmethod
    def fom_observable_storage_path(cls, storage_path: Optional[str] = None)->"LlmOperationCollector":
        cls = cls()        
        env_path = os.environ.get("OBSERVABILITY_DATA_DEFAULT_FILE")
        if storage_path:
            cls.storage_path = storage_path
        elif env_path:
            cls.storage_path = storage_path        
        else:
            cls.storage_path = Path(DEFAULT_OBSERVABILITY_DIR) / DEFAULT_OBSERVABILITY_FILE        
        return cls