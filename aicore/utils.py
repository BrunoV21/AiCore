from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from fastmcp.exceptions import FastMCPError
from json import JSONDecodeError
from functools import wraps
import requests
import asyncio
import time

from aicore.models import BalanceError, FastMcpError
from aicore.logger import _logger
from aicore.const import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_WAIT_MIN,
    DEFAULT_WAIT_MAX,
    DEFAULT_WAIT_EXP_MULTIPLIER
)

def should_retry(exception: Exception) -> bool:
    """Return True if the request should be retried (i.e., error is not 400)"""
    # Don't retry KeyboardInterrupt
    if isinstance(exception, KeyboardInterrupt):
        return False
    
    if isinstance(exception, NotImplementedError):
        return False
    
    if isinstance(exception, asyncio.CancelledError):
        return False
    
    # Don't retry JSONDecodeError
    if isinstance(exception, JSONDecodeError):
        return False
    
    if isinstance(exception, FastMcpError):
        return False
    
    if isinstance(exception, FastMCPError):
        return False
        
    # Don't retry BalanceError instances
    if isinstance(exception, BalanceError):
        return False
        
    # Don't retry balance-related errors
    if is_out_of_balance(exception):
        return False
    
    if "400" in str(exception):
        return False

    # Then check if it's an HTTP 400 error (but not balance-related)
    if isinstance(exception, requests.exceptions.HTTPError):
        if getattr(exception, "response", None) and exception.response.status_code == 400:
            return False 
    
    # For all other cases, retry
    return True

def get_provider(exception_str) -> str:
    if "Anthropic" in exception_str:
        return "Anthropic"
    else:
        return "unknown provider"

def is_out_of_balance(exception: Exception) -> bool:
    # First check for our test simulator or actual BalanceError
    if exception.__class__.__name__ == "BalanceErrorSimulator" or isinstance(exception, BalanceError):
        return True
        
    # Check for credit balance in exception message
    exception_str = str(exception)
    if "credit balance" in exception_str.lower():
        return True
        
    if isinstance(exception, requests.exceptions.HTTPError):
        if str(getattr(exception, "response", None)) and exception.response.status_code == 400:
            try:
                error_data = exception.response.json()
                error_message = error_data.get("error", {}).get("message", "")
                if error_message and ("credit balance" in error_message.lower() or "credit" in error_message.lower()):
                    return True
            except Exception:
                error_message = str(exception)
                if "credit balance" in error_message.lower() or "credit" in error_message.lower():
                    return True
            
    # Check for 400 status code with credit/balance keywords
    if "400" in exception_str and ("credit" in exception_str.lower() or "balance" in exception_str.lower()):
        return True
        
    return False

def wait_for_retry(retry_state):
    """Log retry information before sleeping"""
    attempt_number = retry_state.attempt_number
    next_attempt_in = retry_state.next_action.sleep  # Time until next retry in seconds
    
    last_exception = retry_state.outcome.exception()
    exception_str = str(last_exception)
    
    # Handle Retry-After header if present (for rate limiting)
    retry_after = None
    if hasattr(last_exception, "response") and last_exception.response is not None:
        if last_exception.response.status_code == 429:
            retry_after = last_exception.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                next_attempt_in = int(retry_after)
    
    # Format the wait time for display
    if next_attempt_in >= 1:
        wait_time_str = f"{next_attempt_in:.1f} seconds"
    else:
        wait_time_str = f"{next_attempt_in*1000:.0f} milliseconds"
    
    
    if attempt_number == DEFAULT_MAX_ATTEMPTS:
        _logger.logger.warning(
            f"Attempt {attempt_number}/{DEFAULT_MAX_ATTEMPTS} failed."
        )
    else:
        # Log the warning message
        _logger.logger.warning(
            f"Attempt {attempt_number}/{DEFAULT_MAX_ATTEMPTS} failed. "
            f"Retrying in {wait_time_str}. Error: {exception_str}"
        )
        
        # Sleep if there's a Retry-After header
        if retry_after and retry_after.isdigit():
            time.sleep(next_attempt_in)

def retry_on_failure(func):
    """
    Async-aware decorator for retrying API calls on all errors except 400 errors.
    Logs retry attempts with wait times.
    """
    # Create the retry decorator
    retry_decorator = retry(
        stop=stop_after_attempt(DEFAULT_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=DEFAULT_WAIT_EXP_MULTIPLIER,
            min=DEFAULT_WAIT_MIN,
            max=DEFAULT_WAIT_MAX
        ),
        retry=retry_if_exception(should_retry),
        before_sleep=wait_for_retry,
        reraise=True  # Important: must reraise to propagate exceptions
    )

    if asyncio.iscoroutinefunction(func):
        # Async version
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                # Apply the retry decorator to a local async function
                @retry_decorator
                async def retry_func(*inner_args, **inner_kwargs):
                    try:
                        return await func(*inner_args, **inner_kwargs)
                    except KeyboardInterrupt:
                        # Immediately break out of retry loop on KeyboardInterrupt
                        raise
                
                return await retry_func(*args, **kwargs)
            except asyncio.CancelledError:
                raise
            except KeyboardInterrupt:
                # Always propagate KeyboardInterrupt without logging
                raise
            except BalanceError:
                # Always propagate BalanceError
                raise
            except JSONDecodeError:
                raise
            except Exception as e:
                # Special handling for balance-like errors
                if is_out_of_balance(e):
                    # Create and raise a BalanceError
                    error_message = str(e)
                    provider = get_provider(error_message)
                    raise BalanceError(provider=provider, message=error_message, status_code=400)
                
                # For other errors, log and return None
                _logger.logger.error(
                    f"Function {func.__name__} failed with error: {str(e)}"
                )
                return None
        return async_wrapper
    else:
        # Sync version (same pattern as async)
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                # Apply the retry decorator
                @retry_decorator
                def retry_func(*inner_args, **inner_kwargs):
                    try:
                        return func(*inner_args, **inner_kwargs)
                    except KeyboardInterrupt:
                        # Immediately break out of retry loop
                        raise
                
                return retry_func(*args, **kwargs)
            except KeyboardInterrupt:
                # Always propagate KeyboardInterrupt without logging
                raise
            except BalanceError:
                # Always propagate BalanceError
                raise            
            except JSONDecodeError:
                raise
            except Exception as e:
                # Special handling for balance-like errors
                if is_out_of_balance(e):
                    # Create and raise a BalanceError
                    error_message = str(e)
                    provider = get_provider(error_message)
                    raise BalanceError(provider=provider, message=error_message, status_code=400)
                
                # For other errors, log and return None
                _logger.logger.error(
                    f"Function {func.__name__} failed with error: {str(e)}"
                )
                return None
        return sync_wrapper

def raise_on_balance_error(func):
    """
    Async-aware decorator that intercepts API calls and raises a BalanceError if
    the error indicates insufficient credit balance.
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BalanceError:
            # Already a BalanceError, just re-raise
            raise
        except Exception as e:
            if is_out_of_balance(e):
                error_message = str(e)
                provider = get_provider(error_message)
                raise BalanceError(provider=provider, message=error_message, status_code=400)
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BalanceError:
            # Already a BalanceError, just re-raise
            raise
        except Exception as e:
            if is_out_of_balance(e):
                error_message = str(e)
                provider = get_provider(error_message)
                raise BalanceError(provider=provider, message=error_message, status_code=400)
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper