import pytest
import time
import requests
import asyncio
from unittest.mock import patch, MagicMock

# Import the decorators from your module
from aicore.utils import (
    retry_on_failure,
    raise_on_balance_error,
    DEFAULT_MAX_ATTEMPTS,
    BalanceError,
    is_out_of_balance,
    should_retry
)

def create_http_error(status_code=429, retry_after=None, text=""):
    """Create a fake requests.HTTPError with specified status code."""
    response = requests.models.Response()
    response.status_code = status_code
    response._content = text.encode() if text else b''
    if retry_after is not None:
        response.headers['Retry-After'] = str(retry_after)
    error = requests.exceptions.HTTPError(f"{status_code} Error", response=response)
    return error

class CustomException(Exception):
    """Generic custom exception for testing"""
    pass

class BalanceErrorSimulator(Exception):
    """Simulates balance error with 400 status and credit message"""
    def __init__(self):
        self.response = MagicMock()
        self.response.status_code = 400
        self.response.text = "credit balance is too low"
        self.response.json.return_value = {"error": {"message": "credit balance is too low"}}
        super().__init__("credit balance is too low")

    def __str__(self):
        return f"{self.response.status_code} {self.response.text}"

# Tests for helper functions
def test_should_retry():
    """Test the should_retry function logic"""
    # Should retry normal exceptions
    assert should_retry(Exception("Normal error")) is True
    assert should_retry(CustomException("Custom error")) is True
    
    # Should not retry 400 errors
    assert should_retry(create_http_error(400)) is False
    
    # Should retry other HTTP errors
    assert should_retry(create_http_error(429)) is True
    assert should_retry(create_http_error(500)) is True
    
    # Should not retry balance errors
    assert should_retry(BalanceErrorSimulator()) is False

def test_is_out_of_balance():
    """Test the is_out_of_balance function logic"""
    # Should detect balance errors
    assert is_out_of_balance(BalanceErrorSimulator()) is True
    
    # Should detect HTTP errors with balance messages
    balance_error = create_http_error(400, text='{"error": {"message": "credit balance is too low"}')
    balance_error.response.json = MagicMock(return_value={"error": {"message": "credit balance is too low"}})
    assert is_out_of_balance(balance_error) is True
    
    # Should not flag non-balance errors
    assert is_out_of_balance(Exception("Normal error")) is False
    assert is_out_of_balance(create_http_error(429)) is False

# Sync Tests
def test_retry_on_generic_error_sync(monkeypatch):
    """Test that generic errors are retried in sync functions"""
    call_count = 0
    sleep_calls = []

    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_failure
    def sometimes_fail():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CustomException("Temporary failure")
        return "success"

    result = sometimes_fail()
    assert result == "success"
    assert call_count == 3
    assert len(sleep_calls) == 2  # Should have slept between attempts

def test_max_retries_reached_sync(monkeypatch):
    """Test that max retries are respected in sync functions"""
    call_count = 0
    sleep_calls = []

    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_failure
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise CustomException("Persistent failure")

    result = always_fail()
    assert result is None
    assert call_count == DEFAULT_MAX_ATTEMPTS
    assert len(sleep_calls) == DEFAULT_MAX_ATTEMPTS - 1  # Should sleep between each attempt

def test_no_retry_on_400_sync():
    """Test that 400 errors are not retried in sync functions"""
    call_count = 0

    @retry_on_failure
    def fail_with_400():
        nonlocal call_count
        call_count += 1
        raise create_http_error(400)

    result = fail_with_400()
    assert result is None
    assert call_count == 1  # Should only call once, no retries

def test_balance_error_conversion_sync():
    """Test that balance errors are properly converted in sync functions"""
    call_count = 0

    @raise_on_balance_error
    @retry_on_failure
    def fail_with_balance_error():
        nonlocal call_count
        call_count += 1
        raise BalanceErrorSimulator()

    with pytest.raises(BalanceError) as exc_info:
        fail_with_balance_error()
    
    assert "credit balance is too low" in str(exc_info.value)
    assert call_count == 1  # Should only call once, no retries for balance errors

def test_retry_with_http_429_sync(monkeypatch):
    """Test retry behavior with HTTP 429 (rate limit) errors"""
    call_count = 0
    sleep_calls = []

    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))

    @retry_on_failure
    def fail_with_rate_limit():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise create_http_error(429, retry_after="2")
        return "success"

    result = fail_with_rate_limit()
    assert result == "success"
    assert call_count == 3
    assert len(sleep_calls) >= 2  # Should have slept between attempts

# # Async Tests
@pytest.mark.asyncio
async def test_retry_on_generic_error_async(monkeypatch):
    """Test that generic errors are retried in async functions"""
    call_count = 0
    sleep_calls = []

    # Mock asyncio.sleep
    async def mock_sleep(t):
        sleep_calls.append(t)
        return

    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    @retry_on_failure
    async def sometimes_fail():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CustomException("Temporary failure")
        return "success"

    result = await sometimes_fail()
    assert result == "success"
    assert call_count == 3
    assert len(sleep_calls) == 2  # Should have slept between attempts

@pytest.mark.asyncio
async def test_max_retries_reached_async(monkeypatch):
    """Test that max retries are respected in async functions"""
    call_count = 0
    sleep_calls = []

    # Mock asyncio.sleep
    async def mock_sleep(t):
        sleep_calls.append(t)
        return

    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    @retry_on_failure
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise CustomException("Persistent failure")

    result = await always_fail()
    assert result is None
    assert call_count == DEFAULT_MAX_ATTEMPTS
    assert len(sleep_calls) == DEFAULT_MAX_ATTEMPTS - 1  # Should sleep between each attempt

@pytest.mark.asyncio
async def test_no_retry_on_400_async():
    """Test that 400 errors are not retried in async functions"""
    call_count = 0

    @retry_on_failure
    async def fail_with_400():
        nonlocal call_count
        call_count += 1
        raise create_http_error(400)

    result = await fail_with_400()
    assert result is None
    assert call_count == 1  # Should only call once, no retries

@pytest.mark.asyncio
async def test_balance_error_conversion_async():
    """Test that balance errors are properly converted in async functions"""
    call_count = 0

    @raise_on_balance_error
    @retry_on_failure
    async def fail_with_balance_error():
        nonlocal call_count
        call_count += 1
        raise BalanceErrorSimulator()

    with pytest.raises(BalanceError) as exc_info:
        await fail_with_balance_error()
    
    assert "credit balance is too low" in str(exc_info.value)
    assert call_count == 1  # Should only call once, no retries for balance errors

@pytest.mark.asyncio
async def test_retry_with_http_429_async(monkeypatch):
    """Test retry behavior with HTTP 429 (rate limit) errors in async functions"""
    call_count = 0
    sleep_calls = []

    # Mock asyncio.sleep
    async def mock_sleep(t):
        sleep_calls.append(t)
        return

    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    @retry_on_failure
    async def fail_with_rate_limit():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise create_http_error(429, retry_after="2")
        return "success"

    result = await fail_with_rate_limit()
    assert result == "success"
    assert call_count == 3
    assert len(sleep_calls) == 2  # Should have slept between attempts

def test_decorator_order_handling():
    """Test that decorator order is correct (retry first, then balance check)"""
    call_count = 0

    @raise_on_balance_error
    @retry_on_failure
    def mixed_failure():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CustomException("Temporary failure")
        raise BalanceError(provider="dummy", message="str")

    with pytest.raises(BalanceError):  # More specific exception
        mixed_failure()
    
    assert call_count == 3  # Should have retried before hitting balance error

@pytest.mark.asyncio
async def test_decorator_order_handling_async():
    """Test that decorator order is correct for async functions"""
    call_count = 0

    @raise_on_balance_error
    @retry_on_failure
    async def mixed_failure():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CustomException("Temporary failure")
        raise BalanceError(provider="dummy", message="str")

    with pytest.raises(BalanceError):  # More specific exception
        await mixed_failure()
    
    assert call_count == 3  # Should have retried before hitting balance error

# def test_returning_none_doesnt_trigger_error():
#     """Test that functions that return None don't trigger errors"""
#     call_count = 0

#     @retry_on_failure
#     def return_none():
#         nonlocal call_count
#         call_count += 1
#         return None

#     result = return_none()
#     assert result is None
#     assert call_count == 1  # Should only call once, no errors

# def test_retry_on_specific_error_types():
#     """Test retry behavior with different error types"""
#     results = []

#     @retry_on_failure
#     def raise_different_errors():
#         if not results:
#             results.append("attempt1")
#             raise TimeoutError("Connection timeout")
#         elif len(results) == 1:
#             results.append("attempt2")
#             raise ConnectionError("Network error")
#         else:
#             results.append("success")
#             return "success"

#     result = raise_different_errors()
#     assert result == "success"
#     assert len(results) == 3
#     assert "attempt1" in results
#     assert "attempt2" in results
#     assert "success" in results