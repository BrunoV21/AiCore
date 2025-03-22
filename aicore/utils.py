from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from functools import wraps
import requests
import time

from aicore.logger import _logger
from aicore.const import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_WAIT_MIN,
    DEFAULT_WAIT_MAX,
    DEFAULT_WAIT_EXP_MULTIPLIER
)

def is_rate_limited(exception):
    """
    Determine if an exception is due to rate limiting.

    This covers:
      - requests.HTTPError with a response status code of 429.
      - Any exception whose string representation includes '429',
        which can catch errors from other providers.
    """
    # Check if it's a requests.HTTPError with a 429 status.
    if isinstance(exception, requests.exceptions.HTTPError):
        if getattr(exception, "response", None) and exception.response.status_code == 429:
            return True
    # Fallback: Check if '429' appears in the exception message.
    if "429" in str(exception):
        return True
    return False

def wait_for_retry(retry_state):
    """
    If the exception includes a Retry-After header, wait accordingly.

    This checks if the exception has a response with headers and uses the
    Retry-After header to determine the wait time.
    """
    last_exception = retry_state.outcome.exception()
    # Only check if the exception has a response attribute.
    if hasattr(last_exception, "response") and last_exception.response is not None:
        if last_exception.response.status_code == 429:
            retry_after = last_exception.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait_time = int(retry_after)
                _logger.logger.error(f"Rate limited! Waiting for {wait_time} seconds before retrying...")
                time.sleep(wait_time)

def retry_on_rate_limit(func):
    """
    Custom decorator for retrying API calls only on 429 rate-limit errors.

    Retries up to 5 times using an exponential backoff, and it will also
    pause for a specified time if a 'Retry-After' header is present.

    Additionally, if all retries fail (or a non-rate-limit exception occurs),
    the exception is caught inside the decorator and the function returns None,
    ensuring that no exception is raised to the caller.
    """
    # Create a tenacity-decorated function.
    decorated = retry(
        stop=stop_after_attempt(DEFAULT_MAX_ATTEMPTS), # Retry up to 5 times
        wait=wait_exponential(
            multiplier=DEFAULT_WAIT_EXP_MULTIPLIER,    # Exponential backoff
            min=DEFAULT_WAIT_MIN,
            max=DEFAULT_WAIT_MAX
        ),
        retry=retry_if_exception(is_rate_limited),     # Only retry for 429 errors
        before_sleep=wait_for_retry                    # Handle dynamic waiting based on Retry-After
    )(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return decorated(*args, **kwargs)
        except Exception as e:
            _logger.logger.error(f"Function {func.__name__} failed after retries with error: {e}")
            return None
    return wrapper