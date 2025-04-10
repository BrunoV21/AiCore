from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from functools import wraps
import requests
import time

from aicore.models import BalanceError
from aicore.logger import _logger
from aicore.const import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_WAIT_MIN,
    DEFAULT_WAIT_MAX,
    DEFAULT_WAIT_EXP_MULTIPLIER
)

def is_rate_limited(exception):
    if isinstance(exception, requests.exceptions.HTTPError):
        if getattr(exception, "response", None) and exception.response.status_code == 429:
            return True
        elif getattr(exception, "response", None) and "overload" in exception.response.text:
            return True
        elif getattr(exception, "response", None) and "overload" in exception.response.text:
            return True
    if "429" in str(exception):
        return True
    elif "overload" in str(exception).lower():
        return True
    return False

def get_provider(exception_str) -> str:
    if "Anthropic" in exception_str:
        return "Anthropic"
    else:
        return "unknown provider"

def is_out_of_balance(exception: Exception) -> bool:
    if isinstance(exception, requests.exceptions.HTTPError):
        if getattr(exception, "response", None) and exception.response.status_code == 400:
            try:
                error_data = exception.response.json()
                error_message = error_data.get("error", {}).get("message", "")
            except Exception:
                error_message = str(exception)
            if "credit balance is too low" in error_message:
                return True
            if "credit" in error_message:
                return True
            
    exception_str = str(exception)
    if "400" in exception_str and ("credit" in exception_str or "balance" in exception_str):
        return True
    return False

def wait_for_retry(retry_state):
    last_exception = retry_state.outcome.exception()
    if hasattr(last_exception, "response") and last_exception.response is not None:
        if last_exception.response.status_code == 429:
            retry_after = last_exception.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait_time = int(retry_after)
                _logger.logger.error(f"Rate limited! Waiting for {wait_time} seconds before retrying...")
                time.sleep(wait_time)

def retry_on_rate_limit(func):
    """
    Async-aware decorator for retrying API calls only on 429 errors.
    """
    # Using tenacity's retry for async functions.
    decorated = retry(
        stop=stop_after_attempt(DEFAULT_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=DEFAULT_WAIT_EXP_MULTIPLIER,
            min=DEFAULT_WAIT_MIN,
            max=DEFAULT_WAIT_MAX
        ),
        retry=retry_if_exception(is_rate_limited),
        before_sleep=wait_for_retry
    )(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return decorated(*args, **kwargs)
        except Exception as e:
            # If a BalanceError was raised inside, let it propagate.
            if isinstance(e, BalanceError):
                raise
            _logger.logger.error(f"Function {func.__name__} failed after retries with error: {e}")
            return None
    return wrapper

def raise_on_balance_error(func):
    """
    Async-aware decorator that intercepts API calls and raises a BalanceError if
    the error indicates insufficient credit balance.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if is_out_of_balance(e):
                error_message = str(e)
                provider = get_provider(error_message)
                raise BalanceError(provider=provider, message=error_message, status_code=400)
            raise
    return wrapper