from typing import Optional

class AiCoreBaseException(Exception):
    def __init__(self, provider :str, message :str, status_code :Optional[int]=401):
        self.provider = provider
        self.message = message
        self.status_code = status_code

    def __str__(self)->str:
        return str(self.__dict__)

class AuthenticationError(AiCoreBaseException):
    ...

class ModelError(AiCoreBaseException):
    def __init__(self, provider :str, message :str, supported_models :Optional[list[str]]=None, status_code :Optional[int]=401):
        super().__init__(provider, message, status_code)
        self.supported_models= supported_models

    @classmethod
    def from_model(cls, model :str, provider :str, supported_models :Optional[list[str]]=None, status_code :Optional[int]=401)->"ModelError":
        return cls(
            provider=provider,
            message=f"Invalid model: {model}",
            supported_models=supported_models,
            status_code=status_code
        )
    
class BalanceError(AiCoreBaseException):
    ...