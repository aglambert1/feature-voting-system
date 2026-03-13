"""
Database session helper for MCP server.

Reuses the same database configuration as the main app.
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings


_connect_args = (
    {"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@contextmanager
def get_session():
    """Provide a transactional database session scope."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispatch_task(task, *args, **kwargs):
    """Dispatch a Celery task with automatic broker reconnection.

    On a stale broker connection (e.g. Redis restarted), closes the
    broken connection pool and retries once with a fresh connection.
    Returns the AsyncResult on success, or raises on persistent failure.
    """
    import logging
    from kombu.exceptions import OperationalError

    logger = logging.getLogger(__name__)

    try:
        return task.delay(*args, **kwargs)
    except OperationalError:
        logger.warning("Broker connection failed, reconnecting and retrying...")
        try:
            task.app.close()
        except Exception:
            pass
        return task.delay(*args, **kwargs)
