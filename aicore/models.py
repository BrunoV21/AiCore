from typing import Optional

class AiCoreBaseException(Exception):
    def __init__(self, provider :str, message :str, status_code :int=401):
        self.provider = provider
        self.message = message
        self.status_code = status_code

    def __str__(self)->str:
        return str(self.__dict__)

class AuthenticationError(AiCoreBaseException):
    ...

class ModelError(AiCoreBaseException):
    ...

    @classmethod
    def from_model(cls, model :str, provider :str, status_code :Optional[int]=401)->"ModelError":
        return cls(
            provider=provider,
            message=f"Invalid model: {model}",
            status_code=status_code
        )
    
class BalanceError(AiCoreBaseException):
    ...