from pydantic import BaseModel, model_validator
from typing import Dict, Self, Optional, Any
from aicore.llm.config import LlmConfig
import ulid

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class ChatRequest(BaseModel):
    session_id: str=""
    message: str
    model_params: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def set_session_id(self)->Self:
        if not self.session_id:
            self.session_id = ulid.ulid()
        return self