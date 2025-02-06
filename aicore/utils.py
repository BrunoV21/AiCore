from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from functools import wraps
import requests
import time

from aicore.logger import _logger


def is_rate_limited(exception):
    """Retry only when the response status code is 429 (Rate Limited)."""
    return (
        isinstance(exception, requests.exceptions.HTTPError) and 
        exception.response.status_code == 429
    )

def wait_for_retry(retry_state):
    """Check if the response has a Retry-After header and wait accordingly."""
    last_exception = retry_state.outcome.exception()
    if isinstance(last_exception, requests.exceptions.HTTPError) and last_exception.response.status_code == 429:
        retry_after = last_exception.response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            wait_time = int(retry_after)
            _logger.logger.error(f"Rate limited! Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)

def retry_on_rate_limit(func):
    """Custom decorator for retrying API calls only on 429 rate-limit errors."""
    @retry(
        stop=stop_after_attempt(5),  # Retry up to 5 times
        wait=wait_exponential(multiplier=1, min=1, max=60),  # Exponential backoff
        retry=retry_if_exception(is_rate_limited),  # Retry only for 429 errors
        before_sleep=wait_for_retry  # Handle 429 Retry-After dynamically
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper