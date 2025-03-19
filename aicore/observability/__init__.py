
"""
Observability module for tracking LLM completion operations.

This module provides tools to collect, store, and visualize data about LLM operations,
including completion arguments, responses, and performance metrics.
"""
try:
    from aicore.observability.collector import LlmOperationCollector, LlmOperationRecord
    from aicore.observability.dashboard import ObservabilityDashboard

    __all__ = [
        "LlmOperationCollector", "LlmOperationRecord", "ObservabilityDashboard"
    ]
except ModuleNotFoundError:
    ...