"""
Utility functions for analyzing LLM operation statistics from JSON files and database.

These functions can be called in isolation and provide accumulated statistics
for specific sessions or across all sessions.
"""

import os
import json
import orjson
import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional
from collections import defaultdict
from aicore.const import DEFAULT_OBSERVABILITY_DIR


def get_json_stats(session_id: Optional[str] = None, storage_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get accumulated statistics from JSON chunk files.

    This function reads from the chunked JSON storage and calculates aggregated metrics.
    It's fast and works with recent operational data without requiring database access.

    Args:
        session_id: Optional session ID to filter by. If None, accumulates across all sessions.
        storage_path: Optional path to observability data root directory.
                     If None, uses OBSERVABILITY_DATA_ROOT env var or default.

    Returns:
        Dictionary containing accumulated statistics:
        {
            "total_calls": int,              # Total number of LLM calls
            "total_tokens": int,             # Sum of all tokens (input + output)
            "input_tokens": int,             # Total input tokens
            "output_tokens": int,            # Total output tokens
            "cached_tokens": int,            # Total cached tokens
            "total_cost": float,             # Total cost across all calls
            "average_cost": float,           # Average cost per call
            "total_latency_ms": float,       # Total latency in milliseconds
            "average_latency_ms": float,     # Average latency per call
            "success_count": int,            # Number of successful calls
            "error_count": int,              # Number of failed calls
            "success_rate": float,           # Percentage of successful calls
            "costs_by_provider_model": dict, # Cost breakdown by "provider/model"
            "calls_by_provider_model": dict, # Call count by "provider/model"
            "tokens_by_provider_model": dict # Token count by "provider/model"
        }

    Example:
        >>> stats = get_json_stats(session_id="my-session-123")
        >>> print(f"Total cost: ${stats['total_cost']:.4f}")
        >>> print(f"Total calls: {stats['total_calls']}")
    """
    # Determine storage path
    if storage_path is None:
        storage_path = os.environ.get("OBSERVABILITY_DATA_ROOT") or \
                      os.environ.get("OBSERVABILITY_DATA_DEFAULT_FILE") or \
                      DEFAULT_OBSERVABILITY_DIR

    root_dir = Path(storage_path)

    if not root_dir.exists():
        return _empty_stats()

    # Determine which session directories to process
    if session_id:
        # Sanitize session_id for filesystem safety
        safe_session_id = session_id.replace("/", "_").replace("\\", "_").replace(":", "_") or "default"
        session_dirs = [root_dir / safe_session_id]
    else:
        # Load all sessions
        session_dirs = [d for d in root_dir.iterdir() if d.is_dir()]

    # Initialize accumulators
    total_calls = 0
    total_tokens = 0
    input_tokens = 0
    output_tokens = 0
    cached_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    success_count = 0
    error_count = 0

    costs_by_provider_model = defaultdict(float)
    calls_by_provider_model = defaultdict(int)
    tokens_by_provider_model = defaultdict(int)

    # Process all chunks from all sessions
    for session_dir in session_dirs:
        if not session_dir.exists():
            continue

        # Get all chunk files sorted by number
        chunk_files = sorted(session_dir.glob("*.json"), key=lambda p: int(p.stem))

        for chunk_file in chunk_files:
            try:
                with open(chunk_file, 'rb') as f:
                    chunk_data = orjson.loads(f.read())

                    if not isinstance(chunk_data, list):
                        continue

                    # Process each record in the chunk
                    for record in chunk_data:
                        total_calls += 1

                        # Token metrics
                        rec_input = record.get("input_tokens", 0) or 0
                        rec_output = record.get("output_tokens", 0) or 0
                        rec_cached = record.get("cached_tokens", 0) or 0
                        rec_total = rec_input + rec_output

                        input_tokens += rec_input
                        output_tokens += rec_output
                        cached_tokens += rec_cached
                        total_tokens += rec_total

                        # Cost metrics
                        rec_cost = record.get("cost", 0) or 0
                        total_cost += rec_cost

                        # Latency metrics
                        rec_latency = record.get("latency_ms", 0) or 0
                        total_latency += rec_latency

                        # Success/error tracking
                        if record.get("error_message"):
                            error_count += 1
                        else:
                            success_count += 1

                        # Provider/model breakdown
                        provider = record.get("provider", "unknown")

                        # Get model from completion_args or directly from record
                        completion_args = record.get("completion_args", {})
                        if isinstance(completion_args, str):
                            try:
                                completion_args = json.loads(completion_args)
                            except Exception:
                                completion_args = {}

                        model = completion_args.get("model") or record.get("model", "unknown")
                        provider_model = f"{provider}/{model}"

                        costs_by_provider_model[provider_model] += rec_cost
                        calls_by_provider_model[provider_model] += 1
                        tokens_by_provider_model[provider_model] += rec_total

            except (orjson.JSONDecodeError, FileNotFoundError, ValueError) as e:
                # Skip corrupted or missing chunk files
                continue

    # Calculate averages
    average_cost = total_cost / total_calls if total_calls > 0 else 0.0
    average_latency = total_latency / total_calls if total_calls > 0 else 0.0
    success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0.0

    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_cost": round(total_cost, 6),
        "average_cost": round(average_cost, 6),
        "total_latency_ms": round(total_latency, 2),
        "average_latency_ms": round(average_latency, 2),
        "success_count": success_count,
        "error_count": error_count,
        "success_rate": round(success_rate, 2),
        "costs_by_provider_model": dict(costs_by_provider_model),
        "calls_by_provider_model": dict(calls_by_provider_model),
        "tokens_by_provider_model": dict(tokens_by_provider_model)
    }


async def async_get_json_stats(session_id: Optional[str] = None, storage_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get accumulated statistics from JSON chunk files asynchronously (non-blocking).

    This is the async version of get_json_stats() that uses aiofiles for non-blocking I/O.
    Perfect for use in async applications and high-concurrency scenarios.

    Args:
        session_id: Optional session ID to filter by. If None, accumulates across all sessions.
        storage_path: Optional path to observability data root directory.
                     If None, uses OBSERVABILITY_DATA_ROOT env var or default.

    Returns:
        Dictionary containing accumulated statistics (same structure as get_json_stats)

    Example:
        >>> stats = await async_get_json_stats(session_id="my-session-123")
        >>> print(f"Total cost: ${stats['total_cost']:.4f}")
        >>> print(f"Total calls: {stats['total_calls']}")
    """
    # Determine storage path
    if storage_path is None:
        storage_path = os.environ.get("OBSERVABILITY_DATA_ROOT") or \
                      os.environ.get("OBSERVABILITY_DATA_DEFAULT_FILE") or \
                      DEFAULT_OBSERVABILITY_DIR

    root_dir = Path(storage_path)

    if not root_dir.exists():
        return _empty_stats()

    # Determine which session directories to process
    if session_id:
        # Sanitize session_id for filesystem safety
        safe_session_id = session_id.replace("/", "_").replace("\\", "_").replace(":", "_") or "default"
        session_dirs = [root_dir / safe_session_id]
    else:
        # Load all sessions
        session_dirs = [d for d in root_dir.iterdir() if d.is_dir()]

    # Initialize accumulators
    total_calls = 0
    total_tokens = 0
    input_tokens = 0
    output_tokens = 0
    cached_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    success_count = 0
    error_count = 0

    costs_by_provider_model = defaultdict(float)
    calls_by_provider_model = defaultdict(int)
    tokens_by_provider_model = defaultdict(int)

    # Process all chunks from all sessions
    for session_dir in session_dirs:
        if not session_dir.exists():
            continue

        # Get all chunk files sorted by number
        chunk_files = sorted(session_dir.glob("*.json"), key=lambda p: int(p.stem))

        for chunk_file in chunk_files:
            try:
                # Use aiofiles for async file I/O
                async with aiofiles.open(chunk_file, 'rb') as f:
                    content = await f.read()
                    chunk_data = orjson.loads(content)

                    if not isinstance(chunk_data, list):
                        continue

                    # Process each record in the chunk
                    for record in chunk_data:
                        total_calls += 1

                        # Token metrics
                        rec_input = record.get("input_tokens", 0) or 0
                        rec_output = record.get("output_tokens", 0) or 0
                        rec_cached = record.get("cached_tokens", 0) or 0
                        rec_total = rec_input + rec_output

                        input_tokens += rec_input
                        output_tokens += rec_output
                        cached_tokens += rec_cached
                        total_tokens += rec_total

                        # Cost metrics
                        rec_cost = record.get("cost", 0) or 0
                        total_cost += rec_cost

                        # Latency metrics
                        rec_latency = record.get("latency_ms", 0) or 0
                        total_latency += rec_latency

                        # Success/error tracking
                        if record.get("error_message"):
                            error_count += 1
                        else:
                            success_count += 1

                        # Provider/model breakdown
                        provider = record.get("provider", "unknown")

                        # Get model from completion_args or directly from record
                        completion_args = record.get("completion_args", {})
                        if isinstance(completion_args, str):
                            try:
                                completion_args = json.loads(completion_args)
                            except Exception:
                                completion_args = {}

                        model = completion_args.get("model") or record.get("model", "unknown")
                        provider_model = f"{provider}/{model}"

                        costs_by_provider_model[provider_model] += rec_cost
                        calls_by_provider_model[provider_model] += 1
                        tokens_by_provider_model[provider_model] += rec_total

            except (orjson.JSONDecodeError, FileNotFoundError, ValueError) as e:
                # Skip corrupted or missing chunk files
                continue

    # Calculate averages
    average_cost = total_cost / total_calls if total_calls > 0 else 0.0
    average_latency = total_latency / total_calls if total_calls > 0 else 0.0
    success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0.0

    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_cost": round(total_cost, 6),
        "average_cost": round(average_cost, 6),
        "total_latency_ms": round(total_latency, 2),
        "average_latency_ms": round(average_latency, 2),
        "success_count": success_count,
        "error_count": error_count,
        "success_rate": round(success_rate, 2),
        "costs_by_provider_model": dict(costs_by_provider_model),
        "calls_by_provider_model": dict(calls_by_provider_model),
        "tokens_by_provider_model": dict(tokens_by_provider_model)
    }


async def get_db_stats(
    session_id: Optional[str] = None,
    db_connection_string: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get accumulated statistics from the database asynchronously.

    This function queries the SQLite/PostgreSQL database for complete historical data
    and calculates aggregated metrics. Requires database access.

    Args:
        session_id: Optional session ID to filter by. If None, accumulates across all sessions.
        db_connection_string: Optional async database connection string.
                             If None, uses ASYNC_CONNECTION_STRING env var.

    Returns:
        Dictionary containing accumulated statistics (same structure as get_json_stats):
        {
            "total_calls": int,
            "total_tokens": int,
            "input_tokens": int,
            "output_tokens": int,
            "cached_tokens": int,
            "total_cost": float,
            "average_cost": float,
            "total_latency_ms": float,
            "average_latency_ms": float,
            "success_count": int,
            "error_count": int,
            "success_rate": float,
            "costs_by_provider_model": dict,
            "calls_by_provider_model": dict,
            "tokens_by_provider_model": dict
        }

    Example:
        >>> stats = await get_db_stats(session_id="my-session-123")
        >>> print(f"Total cost: ${stats['total_cost']:.4f}")
        >>> print(f"Success rate: {stats['success_rate']}%")
    """
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import select, func
        from aicore.observability.models import Session, Message, Metric
    except ModuleNotFoundError:
        raise ImportError(
            "Database dependencies not installed. "
            "Run: pip install core-for-ai[sql]"
        )

    # Get connection string
    if db_connection_string is None:
        db_connection_string = os.environ.get("ASYNC_CONNECTION_STRING")

    if not db_connection_string:
        raise ValueError(
            "No database connection string provided. "
            "Set ASYNC_CONNECTION_STRING environment variable or pass db_connection_string parameter."
        )

    # Create async engine
    engine = create_async_engine(db_connection_string)
    async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with async_session_factory() as session:
        try:
            # Build query
            query = (
                select(
                    Metric.provider,
                    Metric.model,
                    Metric.input_tokens,
                    Metric.output_tokens,
                    Metric.cached_tokens,
                    Metric.total_tokens,
                    Metric.cost,
                    Metric.latency_ms,
                    Metric.success,
                    Message.error_message
                )
                .join(Message, Metric.operation_id == Message.operation_id)
                .join(Session, Message.session_id == Session.session_id)
            )

            # Apply session filter if provided
            if session_id:
                query = query.where(Session.session_id == session_id)

            # Execute query
            result = await session.execute(query)
            rows = result.fetchall()

            if not rows:
                return _empty_stats()

            # Initialize accumulators
            total_calls = 0
            total_tokens = 0
            input_tokens = 0
            output_tokens = 0
            cached_tokens = 0
            total_cost = 0.0
            total_latency = 0.0
            success_count = 0
            error_count = 0

            costs_by_provider_model = defaultdict(float)
            calls_by_provider_model = defaultdict(int)
            tokens_by_provider_model = defaultdict(int)

            # Process each row
            for row in rows:
                total_calls += 1

                # Token metrics
                rec_input = row.input_tokens or 0
                rec_output = row.output_tokens or 0
                rec_cached = row.cached_tokens or 0
                rec_total = row.total_tokens or (rec_input + rec_output)

                input_tokens += rec_input
                output_tokens += rec_output
                cached_tokens += rec_cached
                total_tokens += rec_total

                # Cost metrics
                rec_cost = row.cost or 0
                total_cost += rec_cost

                # Latency metrics
                rec_latency = row.latency_ms or 0
                total_latency += rec_latency

                # Success/error tracking
                if row.error_message:
                    error_count += 1
                else:
                    success_count += 1

                # Provider/model breakdown
                provider = row.provider or "unknown"
                model = row.model or "unknown"
                provider_model = f"{provider}/{model}"

                costs_by_provider_model[provider_model] += rec_cost
                calls_by_provider_model[provider_model] += 1
                tokens_by_provider_model[provider_model] += rec_total

            # Calculate averages
            average_cost = total_cost / total_calls if total_calls > 0 else 0.0
            average_latency = total_latency / total_calls if total_calls > 0 else 0.0
            success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0.0

            return {
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "total_cost": round(total_cost, 6),
                "average_cost": round(average_cost, 6),
                "total_latency_ms": round(total_latency, 2),
                "average_latency_ms": round(average_latency, 2),
                "success_count": success_count,
                "error_count": error_count,
                "success_rate": round(success_rate, 2),
                "costs_by_provider_model": dict(costs_by_provider_model),
                "calls_by_provider_model": dict(calls_by_provider_model),
                "tokens_by_provider_model": dict(tokens_by_provider_model)
            }

        except Exception as e:
            await session.rollback()
            raise e
        finally:
            # Ensure engine is disposed
            await engine.dispose()


def delete_session_data(session_id: Optional[str] = None, storage_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete session data from JSON chunk files.

    WARNING: This operation is irreversible. All deleted data cannot be recovered.

    Args:
        session_id: Optional session ID to delete. If None, deletes ALL sessions.
        storage_path: Optional path to observability data root directory.
                     If None, uses OBSERVABILITY_DATA_ROOT env var or default.

    Returns:
        Dictionary containing deletion results:
        {
            "deleted_sessions": List[str],    # List of deleted session IDs
            "deleted_files": int,             # Total number of files deleted
            "deleted_bytes": int,             # Total bytes deleted
            "errors": List[str]               # Any errors encountered during deletion
        }

    Examples:
        >>> # Delete specific session
        >>> result = delete_session_data(session_id="my-session-123")
        >>> print(f"Deleted {result['deleted_files']} files from session")

        >>> # Delete ALL sessions (dangerous!)
        >>> result = delete_session_data()
        >>> print(f"Deleted {len(result['deleted_sessions'])} sessions")
    """
    import shutil

    # Determine storage path
    if storage_path is None:
        storage_path = os.environ.get("OBSERVABILITY_DATA_ROOT") or \
                      os.environ.get("OBSERVABILITY_DATA_DEFAULT_FILE") or \
                      DEFAULT_OBSERVABILITY_DIR

    root_dir = Path(storage_path)

    if not root_dir.exists():
        return {
            "deleted_sessions": [],
            "deleted_files": 0,
            "deleted_bytes": 0,
            "errors": [f"Storage path does not exist: {root_dir}"]
        }

    # Sanitize session_id for filesystem safety
    def _sanitize_session_id(sid: str) -> str:
        return sid.replace("/", "_").replace("\\", "_").replace(":", "_") or "default"

    # Determine which session directories to delete
    if session_id:
        safe_session_id = _sanitize_session_id(session_id)
        session_dirs = [root_dir / safe_session_id]
        session_ids_to_delete = [session_id]
    else:
        # Delete ALL sessions
        session_dirs = [d for d in root_dir.iterdir() if d.is_dir()]
        session_ids_to_delete = [d.name for d in session_dirs]

    # Track deletion results
    deleted_sessions = []
    deleted_files = 0
    deleted_bytes = 0
    errors = []

    for session_dir, original_session_id in zip(session_dirs, session_ids_to_delete):
        if not session_dir.exists():
            errors.append(f"Session directory does not exist: {original_session_id}")
            continue

        try:
            # Count files and bytes before deletion
            dir_files = 0
            dir_bytes = 0

            for chunk_file in session_dir.glob("*.json"):
                if chunk_file.is_file():
                    dir_files += 1
                    dir_bytes += chunk_file.stat().st_size

            # Delete the entire session directory
            shutil.rmtree(session_dir)

            # Update counters
            deleted_sessions.append(original_session_id)
            deleted_files += dir_files
            deleted_bytes += dir_bytes

        except PermissionError as e:
            errors.append(f"Permission denied deleting session '{original_session_id}': {str(e)}")
        except Exception as e:
            errors.append(f"Error deleting session '{original_session_id}': {str(e)}")

    return {
        "deleted_sessions": deleted_sessions,
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "errors": errors
    }


async def async_delete_session_data(session_id: Optional[str] = None, storage_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete session data from JSON chunk files asynchronously (non-blocking).

    This is the async version of delete_session_data() that uses asyncio for non-blocking operations.
    Perfect for use in async applications and high-concurrency scenarios.

    WARNING: This operation is irreversible. All deleted data cannot be recovered.

    Args:
        session_id: Optional session ID to delete. If None, deletes ALL sessions.
        storage_path: Optional path to observability data root directory.
                     If None, uses OBSERVABILITY_DATA_ROOT env var or default.

    Returns:
        Dictionary containing deletion results:
        {
            "deleted_sessions": List[str],    # List of deleted session IDs
            "deleted_files": int,             # Total number of files deleted
            "deleted_bytes": int,             # Total bytes deleted
            "errors": List[str]               # Any errors encountered during deletion
        }

    Examples:
        >>> # Delete specific session
        >>> result = await async_delete_session_data(session_id="my-session-123")
        >>> print(f"Deleted {result['deleted_files']} files from session")

        >>> # Delete ALL sessions (dangerous!)
        >>> result = await async_delete_session_data()
        >>> print(f"Deleted {len(result['deleted_sessions'])} sessions")
    """
    # Determine storage path
    if storage_path is None:
        storage_path = os.environ.get("OBSERVABILITY_DATA_ROOT") or \
                      os.environ.get("OBSERVABILITY_DATA_DEFAULT_FILE") or \
                      DEFAULT_OBSERVABILITY_DIR

    root_dir = Path(storage_path)

    if not root_dir.exists():
        return {
            "deleted_sessions": [],
            "deleted_files": 0,
            "deleted_bytes": 0,
            "errors": [f"Storage path does not exist: {root_dir}"]
        }

    # Sanitize session_id for filesystem safety
    def _sanitize_session_id(sid: str) -> str:
        return sid.replace("/", "_").replace("\\", "_").replace(":", "_") or "default"

    # Determine which session directories to delete
    if session_id:
        safe_session_id = _sanitize_session_id(session_id)
        session_dirs = [root_dir / safe_session_id]
        session_ids_to_delete = [session_id]
    else:
        # Delete ALL sessions
        session_dirs = [d for d in root_dir.iterdir() if d.is_dir()]
        session_ids_to_delete = [d.name for d in session_dirs]

    # Track deletion results
    deleted_sessions = []
    deleted_files = 0
    deleted_bytes = 0
    errors = []

    # Use asyncio to run blocking operations in executor to avoid blocking event loop
    loop = asyncio.get_event_loop()

    async def _delete_session_dir(session_dir: Path, original_session_id: str):
        """Helper to delete a single session directory asynchronously."""
        if not session_dir.exists():
            return None, 0, 0, f"Session directory does not exist: {original_session_id}"

        try:
            # Count files and bytes before deletion (run in executor to avoid blocking)
            def _count_and_delete():
                dir_files = 0
                dir_bytes = 0

                for chunk_file in session_dir.glob("*.json"):
                    if chunk_file.is_file():
                        dir_files += 1
                        dir_bytes += chunk_file.stat().st_size

                # Delete the entire session directory
                import shutil
                shutil.rmtree(session_dir)

                return dir_files, dir_bytes

            dir_files, dir_bytes = await loop.run_in_executor(None, _count_and_delete)
            return original_session_id, dir_files, dir_bytes, None

        except PermissionError as e:
            return None, 0, 0, f"Permission denied deleting session '{original_session_id}': {str(e)}"
        except Exception as e:
            return None, 0, 0, f"Error deleting session '{original_session_id}': {str(e)}"

    # Process all deletions concurrently
    deletion_tasks = [
        _delete_session_dir(session_dir, original_session_id)
        for session_dir, original_session_id in zip(session_dirs, session_ids_to_delete)
    ]

    results = await asyncio.gather(*deletion_tasks)

    # Aggregate results
    for session_id_result, files, bytes_deleted, error in results:
        if error:
            errors.append(error)
        else:
            deleted_sessions.append(session_id_result)
            deleted_files += files
            deleted_bytes += bytes_deleted

    return {
        "deleted_sessions": deleted_sessions,
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "errors": errors
    }


def _empty_stats() -> Dict[str, Any]:
    """Return an empty stats dictionary with all fields set to zero."""
    return {
        "total_calls": 0,
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_cost": 0.0,
        "average_cost": 0.0,
        "total_latency_ms": 0.0,
        "average_latency_ms": 0.0,
        "success_count": 0,
        "error_count": 0,
        "success_rate": 0.0,
        "costs_by_provider_model": {},
        "calls_by_provider_model": {},
        "tokens_by_provider_model": {}
    }
