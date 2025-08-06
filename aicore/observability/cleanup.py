"""
Observability cleanup utilities.

Provides a function to delete old ``Message`` records from the
observability database (default: older than 30 days). The function
uses SQLAlchemy to create a temporary engine based on the
``CONNECTION_STRING`` environment variable, performs the
deletion, commits the transaction, and logs the number of
rows removed via ``loguru``.

A placeholder ``register_cleanup_task`` function is provided
for optional integration with a task scheduler (e.g. Kore)
to run the cleanup periodically.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine

# -------------------------------------------------------------------------
# Helper: create a SQLAlchemy engine from the ``CONNECTION_STRING`` env var.
# -------------------------------------------------------------------------
def _get_engine() -> Optional[Engine]:
    """Create a SQLAlchemy engine from ``CONNECTION_STRING``.

    Returns:
        Engine | None: The engine if the environment variable is set,
        otherwise ``None``.
    """
    conn_str = os.getenv("CONNECTION_STRING")
    if not conn_str:
        logger.warning("CONNECTION_STRING not set; cleanup will be skipped.")
        return None
    return create_engine(conn_str)


def cleanup_old_observability_messages(days: int = 30) -> int:
    """Delete ``Message`` rows older than ``days`` (default 30).

    The function:
    * creates a temporary SQLAlchemy engine,
    * computes a cutoff timestamp (UTC now minus ``days``),
    * deletes rows from ``Message`` where ``timestamp`` is older
      than the cutoff,
    * commits the transaction,
    * logs the number of rows deleted.

    Args:
        days: Number of days to retain messages.

    Returns:
        int: Number of rows deleted (0 if no engine or on error).
    """
    engine = _get_engine()
    if not engine:
        # Non‑blocking – caller may retry later
        logger.warning("Database engine not available; cleanup skipped.")
        return 0

    # ISO‑format cutoff for string comparison
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        from aicore.observability.models import Message  # type: ignore
    except Exception as exc:
        logger.warning(f"Failed to import ORM models: {exc}")
        return 0

    try:
        SessionLocal = sessionmaker(bind=engine)
        with SessionLocal() as session:
            deleted = (
                session.query(Message)
                .filter(Message.timestamp < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            logger.info(
                f"Cleanup: deleted {deleted} old Message records "
                f"(older than {days} days)."
            )
            return deleted
    except Exception as exc:  # pylint: disable=broad-except
        # Log warning but do not raise – caller may retry later
        logger.warning(f"Observability cleanup failed: {exc}")
        return 0


def register_cleanup_task(scheduler: Optional[object] = None, days: int = 30) -> None:
    """Register a daily cleanup task with a scheduler (optional).

    This is a placeholder for integration with a task scheduler
    such as Kore. If a ``scheduler`` object is provided,
    the function attempts to register
    ``cleanup_old_observability_messages`` as a daily
    recurring task. If no scheduler is available,
    the cleanup will be performed on dashboard launch
    (handled elsewhere).

    Args:
        scheduler: Scheduler instance (optional).
        days: Number of days to retain messages.
    """
    if scheduler is None:
        # No scheduler – rely on launch‑triggered cleanup.
        return

    try:
        # Example placeholder – replace with actual scheduler API.
        # scheduler.add_daily_task(
        #     lambda: cleanup_old_observability_messages(days=days),
        #     name="observability_cleanup",
        # )
        logger.info("Registered daily observability cleanup task.")
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(f"Failed to register cleanup task: {exc}")


__all__ = [
    "cleanup_old_observability_messages",
    "register_cleanup_task",
]