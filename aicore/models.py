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

class FastMcpError(Exception):
    """Exception raised for errors in the FastMcp module.
    
    This exception can wrap other exceptions to maintain their details
    while identifying them as coming from the FastMcp module.
    """
    def __init__(self, message=None, original_exception=None):
        if original_exception and not message:
            # Use the original exception's message if no message is provided
            message = str(original_exception)
        
        super().__init__(message)
        self.original_exception = original_exception

    def __str__(self):
        if self.original_exception:
            return f"FastMcpError: {super().__str__()} (Original exception: {self.original_exception.__class__.__name__})"
        return f"FastMcpError: {super().__str__()}"