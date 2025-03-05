
"""
Collector module for capturing LLM completion operations.

This module implements the data collection logic to capture LLM completion arguments
and outputs, providing comprehensive tracking of LLM operations.
"""

import uuid
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List, Union
from pydantic import BaseModel, Field

class LlmOperationRecord(BaseModel):
    """Data model for storing information about a single LLM operation."""
    operation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    provider: str
    model: str
    operation_type: str  # "completion" or "acompletion"
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: float
    success: bool = True
    error_message: Optional[str] = None
    request_args: Dict[str, Any]
    response: Optional[Union[Dict[str, Any], str]] = None
    
    class Config:
        arbitrary_types_allowed = True

class LlmOperationCollector:
    """
    Collects data about LLM operations.
    
    This class provides methods to capture information about LLM completion
    operations, including input arguments, responses, token counts, and latency.
    """
    
    def __init__(self, storage_callback: Optional[Callable[[LlmOperationRecord], None]] = None):
        """
        Initialize the collector.
        
        Args:
            storage_callback: Optional callback function to store operation records
        """
        self.storage_callback = storage_callback
        self._is_enabled = True
    
    @property
    def is_enabled(self) -> bool:
        """Whether collection is enabled."""
        return self._is_enabled
    
    @is_enabled.setter
    def is_enabled(self, value: bool):
        """Set whether collection is enabled."""
        self._is_enabled = value
    
    def record_operation(self, provider: str, model: str, operation_type: str, 
                        request_args: Dict[str, Any], response: Any = None, 
                        input_tokens: Optional[int] = None, output_tokens: Optional[int] = None, 
                        latency_ms: Optional[float] = None, success: bool = True,
                        error_message: Optional[str] = None) -> LlmOperationRecord:
        """
        Record information about an LLM operation.
        
        Args:
            provider: LLM provider name (e.g., "openai", "mistral")
            model: Model name used for the operation
            operation_type: Type of operation ("completion" or "acompletion")
            request_args: Arguments provided to the completion method
            response: Response from the LLM provider
            input_tokens: Number of input tokens (if available)
            output_tokens: Number of output tokens (if available)
            latency_ms: Operation latency in milliseconds
            success: Whether the operation was successful
            error_message: Error message if the operation failed
            
        Returns:
            LlmOperationRecord: Record of the operation
        """
        if not self.is_enabled:
            return None
            
        # Clean request args to remove potentially sensitive or large objects
        cleaned_args = self._clean_request_args(request_args)
        
        record = LlmOperationRecord(
            provider=provider,
            model=model,
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms or 0,
            success=success,
            error_message=error_message,
            request_args=cleaned_args,
            response=response
        )
        
        if self.storage_callback:
            self.storage_callback(record)
            
        return record
    
    def _clean_request_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Clean request arguments to remove sensitive information."""
        cleaned = args.copy()
        # Remove potentially sensitive information like API keys
        cleaned.pop("api_key", None)
        return cleaned