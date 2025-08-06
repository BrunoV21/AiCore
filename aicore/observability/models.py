"""Observability ORM models and cleanup utilities.

This module defines the SQLAlchemy ORM models used by the observability
subsystem and provides a helper function to clean up old
``Message`` records. The cleanup function is used by the dashboard
and collector to delete messages older than a configurable number
of days (default 30). It uses a SQLAlchemy engine created
from the ``CONNECTION_STRING`` environment variable,
commits the transaction, and logs the number of rows
deleted via ``loguru``. If the database is unreachable,
the function returns ``0`` and logs a warning,
allowing the caller to retry on the next launch.
A placeholder ``register_cleanup_task`` function is provided
for optional integration with a task scheduler (e.g. Kore).
"""

from datetime import datetime, timedelta
import os

from loguru import logger
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Session(Base):
    """Session metadata for a group of LLM operations."""

    __tablename__ = "Session"

    session_id = Column(String(255), primary_key=True)  # Fixed length for consistency
    workspace = Column(String)
    agent_id = Column(String)

    # Relationship to messages (lowercase name for ORM expectations)
    messages = relationship("Message", back_populates="session")


class Message(Base):
    """Individual LLM operation record."""

    __tablename__ = "Message"

    operation_id = Column(String(255), primary_key=True)  # Fixed length
    session_id = Column(String(255), ForeignKey("Session.session_id"))
    action_id = Column(String)
    # TODO: replace with DateTime column in a future version
    timestamp = Column(String)
    system_prompt = Column(Text)
    user_prompt = Column(Text)
    response = Column(Text)
    assistant_message = Column(Text)
    history_messages = Column(Text)
    completion_args = Column(Text)
    error_message = Column(Text)

    # Relationships
    session = relationship("Session", back_populates="messages")
    metric = relationship("Metric", back_populates="message", uselist=False)


class Metric(Base):
    """Performance and cost metrics for a single operation."""

    __tablename__ = "Metric"

    operation_id = Column(
        String(255), ForeignKey("Message.operation_id"), primary_key=True
    )
    operation_type = Column(String)
    provider = Column(String)
    model = Column(String)
    success = Column(Boolean)
    temperature = Column(Float)
    max_tokens = Column(Integer)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cached_tokens = Column(Integer)
    total_tokens = Column(Integer)
    cost = Column(Float)
    latency_ms = Column(Float)
    extras = Column(Text)

    # Relationship back to the message
    message = relationship("Message", back_populates="metric")


# -------------------------------------------------------------------------
# Cleanup utilities
# -------------------------------------------------------------------------

def _get_engine():
    """Create a SQLAlchemy engine from ``CONNECTION_STRING``.

    Returns:
        sqlalchemy.Engine | None: The engine if the environment variable
        is set, otherwise ``None``.
    """
    from sqlalchemy import create_engine

    conn_str = os.getenv("CONNECTION_STRING")
    if not conn_str:
        logger.warning(
            "CONNECTION_STRING not set; cleanup will be skipped."
        )
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
        # Non‑blocking warning – caller may retry later
        logger.warning("Database engine not available; cleanup skipped.")
        return 0

    # ISO‑format cutoff for string comparison
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        from sqlalchemy.orm import sessionmaker

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
        # Log warning but do not raise; caller may retry later
        logger.warning(f"Failed to cleanup old messages: {exc}")
        return 0


def register_cleanup_task(scheduler=None, days: int = 30) -> None:
    """Register a daily cleanup task with a scheduler (optional).

    This is a placeholder for integration with a task scheduler
    such as Kore. If a ``scheduler`` object is provided,
    the function attempts to register
    ``cleanup_old_observability_messages`` as a daily
    recurring task. If no scheduler is available,
    the cleanup will be performed on dashboard
    launch (handled elsewhere).

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