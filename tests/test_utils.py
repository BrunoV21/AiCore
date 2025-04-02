import pytest
import time
import requests
import json
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Import the decorators and utilities from your module
from aicore.utils import (
    retry_on_rate_limit, 
    raise_on_balance_error,
    is_rate_limited,
    is_out_of_balance,
    get_provider
)
from aicore.models import BalanceError
from aicore.const import DEFAULT_MAX_ATTEMPTS

# --- Helper Functions and Classes ---

def create_http_error(status_code=429, retry_after=None, json_data=None):
    """
    Create a fake requests.HTTPError with the specified status code.
    Optionally include a Retry-After header and JSON response data.
    """
    response = requests.models.Response()
    response.status_code = status_code
    
    if retry_after is not None:
        response.headers['Retry-After'] = str(retry_after)
    
    if json_data is not None:
        # Properly encode the JSON data
        json_str = json.dumps(json_data)
        response._content = json_str.encode('utf-8')
        # Mock the json method to return our data
        response.json = MagicMock(return_value=json_data)
    
    return requests.exceptions.HTTPError(f"{status_code} Error", response=response)

class Custom429Exception(Exception):
    """
    A custom exception to simulate errors from a provider that
    does not use requests.HTTPError but includes '429' in its message.
    """
    pass

class CustomBalanceException(Exception):
    """
    A custom exception to simulate credit balance errors that don't use
    requests.HTTPError but include balance-related messages.
    """
    pass

# --- Test Cases for retry_on_rate_limit ---

@pytest.mark.asyncio
async def test_retry_http_error(monkeypatch):
    """
    Test that an async function always raising an HTTPError with a 429 status
    is retried up to the maximum attempts, and that the Retry-After logic is invoked.
    
    The decorated function should return None instead of raising an exception.
    """
    call_count = 0
    sleep_calls = []

    # Monkey-patch time.sleep to record sleep durations without actually sleeping
    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_rate_limit
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise create_http_error(retry_after=1)

    result = await always_fail()
    
    # The function should return None after max attempts
    assert result is None
    assert call_count == DEFAULT_MAX_ATTEMPTS
    # Ensure that at least one sleep call was made with the wait time from Retry-After
    assert len(sleep_calls) >= 1
    assert 1 in sleep_calls

@pytest.mark.asyncio
async def test_retry_custom_exception(monkeypatch):
    """
    Test that an async function raising a custom exception with a message 
    containing '429' is retried and eventually returns None.
    """
    call_count = 0

    # For custom exceptions, wait_for_retry won't sleep because there's no response header
    monkeypatch.setattr(time, "sleep", lambda t: None)

    @retry_on_rate_limit
    async def always_fail_custom():
        nonlocal call_count
        call_count += 1
        raise Custom429Exception("Custom provider error: 429 rate limit reached")

    result = await always_fail_custom()
    assert result is None
    assert call_count == DEFAULT_MAX_ATTEMPTS

@pytest.mark.asyncio
async def test_eventual_success(monkeypatch):
    """
    Test that an async function that fails initially with rate-limit errors
    eventually returns successfully after a few attempts.
    """
    call_count = 0
    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_rate_limit
    async def sometimes_fail():
        nonlocal call_count
        call_count += 1
        # Fail the first 2 times, then succeed
        if call_count < 3:
            raise create_http_error(retry_after=0)
        return "success"

    result = await sometimes_fail()
    assert result == "success"
    # The function should have been called exactly 3 times
    assert call_count == 3

@pytest.mark.asyncio
async def test_non_rate_limit_exception(monkeypatch):
    """
    Test that an async function raising an error unrelated to rate limiting
    is not retried and returns None.
    """
    call_count = 0
    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_rate_limit
    async def always_fail_non_rate():
        nonlocal call_count
        call_count += 1
        raise ValueError("A different error occurred")

    result = await always_fail_non_rate()
    # Even though this is not a rate limit error, the exception is caught and the function returns None
    assert result is None
    # Should only be called once because the exception is not retried
    assert call_count == 1
    # No sleep should be triggered
    assert len(sleep_calls) == 0

@pytest.mark.asyncio
async def test_balance_error_propagation():
    """
    Test that when a BalanceError is raised within the async function,
    it propagates through the retry decorator without being caught.
    """
    @retry_on_rate_limit
    async def raise_balance_error():
        raise BalanceError(provider="TestProvider", message="Balance too low", status_code=400)

    with pytest.raises(BalanceError) as excinfo:
        await raise_balance_error()
    
    assert excinfo.value.provider == "TestProvider"
    assert excinfo.value.status_code == 400

@pytest.mark.asyncio
async def test_balance_error_detection_anthropic():
    """
    Test that the raise_on_balance_error decorator correctly identifies
    the provider when it's Anthropic.
    """
    error_message = "Anthropic API Error: Your credit balance is too low"
    
    @raise_on_balance_error
    async def function_with_anthropic_error():
        # Create a custom exception with a 400 status code in the message
        raise Exception(f"400 Bad Request: {error_message}")

    with pytest.raises(BalanceError) as excinfo:
        await function_with_anthropic_error()
    
    assert excinfo.value.provider == "Anthropic"
    assert error_message in excinfo.value.message

@pytest.mark.asyncio
async def test_non_balance_error_propagation():
    """
    Test that the raise_on_balance_error decorator lets non-balance
    errors propagate unchanged.
    """
    original_error = ValueError("Some other error")
    
    @raise_on_balance_error
    async def function_with_other_error():
        raise original_error

    with pytest.raises(ValueError) as excinfo:
        await function_with_other_error()
    
    assert str(excinfo.value) == "Some other error"

@pytest.mark.asyncio
async def test_successful_execution():
    """
    Test that the raise_on_balance_error decorator passes through
    successful results unchanged.
    """
    @raise_on_balance_error
    async def successful_function():
        return "success"

    result = await successful_function()
    assert result == "success"

# --- Test Cases for Utility Functions ---

def test_is_rate_limited():
    """Test the is_rate_limited function with various inputs."""
    # HTTP error with 429 status code
    assert is_rate_limited(create_http_error(status_code=429)) is True
    
    # String containing "429"
    assert is_rate_limited(Exception("Request failed with status 429")) is True
    
    # Non-rate-limit errors
    assert is_rate_limited(ValueError("Some other error")) is False
    assert is_rate_limited(create_http_error(status_code=404)) is False

def test_is_out_of_balance():
    """Test the is_out_of_balance function with various inputs."""
    # HTTP error with balance-related message
    error_response = requests.models.Response()
    error_response.status_code = 400
    
# o    # Create a proper mock for json method
#     json_data = {"error": {"message": "Your credit balance is to low"}}
#     error_response.json = MagicMock(return_value=json_data)
    
    error = requests.exceptions.HTTPError("400 Bad Request", response=error_response)
    assert is_out_of_balance(error) is False
    
    # String containing balance-related message
    assert is_out_of_balance(Exception("400 Bad Request: insufficient credit balance")) is True
    
    # Non-balance errors
    assert is_out_of_balance(ValueError("Some other error")) is False
    assert is_out_of_balance(create_http_error(status_code=404)) is False

def test_get_provider():
    """Test the get_provider function with various inputs."""
    assert get_provider("Anthropic API error: rate limited") == "Anthropic"
    assert get_provider("OpenAI error") == "unknown provider"