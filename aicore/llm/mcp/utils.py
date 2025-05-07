import functools
from typing import Any, Callable, TypeVar
from aicore.models import FastMcpError

# For type annotations
T = TypeVar('T')

def raise_fast_mcp_error(prefix: str = None) -> Callable:
    """
    Decorator that catches any exception raised by the function and 
    re-raises it as a FastMcpError.
    
    Args:
        prefix: Optional string prefix to add to error messages
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except FastMcpError:
                # If it's already a FastMcpError, just re-raise it
                raise
            except Exception as e:
                # Construct the error message
                if prefix:
                    message = f"{prefix}: {str(e)}"
                else:
                    message = str(e)
                
                # Wrap the exception
                raise FastMcpError(message, original_exception=e) from e
                
        return wrapper
    return decorator