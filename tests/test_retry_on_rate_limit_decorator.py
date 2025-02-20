import pytest
import time
import requests

# Import the decorator from your module.
from aicore.utils import retry_on_rate_limit

# --- Helper Functions and Classes ---

def create_http_error(retry_after=None):
    """
    Create a fake requests.HTTPError with a 429 status code.
    Optionally include a Retry-After header.
    """
    response = requests.models.Response()
    response.status_code = 429
    if retry_after is not None:
        response.headers['Retry-After'] = str(retry_after)
    return requests.exceptions.HTTPError("429 Too Many Requests", response=response)

class Custom429Exception(Exception):
    """
    A custom exception to simulate errors from a provider that
    does not use requests.HTTPError but includes '429' in its message.
    """
    pass

# --- Test Cases ---

def test_retry_http_error(monkeypatch):
    """
    Test that a function always raising an HTTPError with a 429 status
    is retried up to the maximum attempts, and that the Retry-After logic
    (here simulated by returning a wait time of 1 second) is invoked.
    
    The decorated function should return None instead of raising an exception.
    """
    call_count = 0
    sleep_calls = []

    # Monkey-patch time.sleep to record sleep durations without actually sleeping.
    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_rate_limit
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise create_http_error(retry_after=1)

    result = always_fail()
    # The function should return None after 5 retries.
    assert result is None
    assert call_count == 5
    # Ensure that at least one sleep call was made with the wait time from Retry-After.
    assert len(sleep_calls) >= 1
    assert 1 in sleep_calls

def test_retry_custom_exception(monkeypatch):
    """
    Test that a function raising a custom exception (without a response attribute)
    but with a message containing '429' is retried and eventually returns None.
    """
    call_count = 0

    # For custom exceptions, wait_for_retry won't sleep because there's no response header.
    monkeypatch.setattr(time, "sleep", lambda t: None)

    @retry_on_rate_limit
    def always_fail_custom():
        nonlocal call_count
        call_count += 1
        raise Custom429Exception("Custom provider error: 429 rate limit reached")

    result = always_fail_custom()
    assert result is None
    assert call_count == 5

def test_eventual_success(monkeypatch):
    """
    Test that a function that fails initially with rate-limit errors
    eventually returns successfully after a few attempts.
    """
    call_count = 0
    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_rate_limit
    def sometimes_fail():
        nonlocal call_count
        call_count += 1
        # Fail the first 2 times, then succeed.
        if call_count < 3:
            raise create_http_error(retry_after=0)
        return "success"

    result = sometimes_fail()
    assert result == "success"
    # The function should have been called exactly 3 times.
    assert call_count == 3

def test_non_rate_limit_exception(monkeypatch):
    """
    Test that a function raising an error unrelated to rate limiting (i.e.
    one that does not include '429') is not retried and returns None.
    """
    call_count = 0
    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_rate_limit
    def always_fail_non_rate():
        nonlocal call_count
        call_count += 1
        raise ValueError("A different error occurred")

    result = always_fail_non_rate()
    # Even though this is not a rate limit error, the exception is caught and the function returns None.
    assert result is None
    # Should only be called once because the exception is not retried.
    assert call_count == 1
    # No sleep should be triggered.
    assert len(sleep_calls) == 0
