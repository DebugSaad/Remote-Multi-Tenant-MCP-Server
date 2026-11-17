"""
Async database engine, session factory, and transaction management.
Connects strictly as app_user (least privilege, subject to Row-Level Security).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.mcp_server.config import settings
from src.mcp_server.shared.context import get_current_user_id

logger = logging.getLogger(__name__)

# Global singleton engine and session factory
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def init_db() -> AsyncEngine:
    """Initialize the async SQLAlchemy engine and session factory once at startup."""
    global _engine, _session_factory
    if _engine is None:
        logger.info("Initializing async database engine with DATABASE_URL...")
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("Async database engine initialized successfully for app_user.")
    return _engine


async def close_db() -> None:
    """Close and dispose of the async database engine on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        logger.info("Closing and disposing of async database engine...")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine closed.")


def get_engine() -> AsyncEngine:
    """Return the active database engine, initializing it if necessary."""
    if _engine is None:
        return init_db()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the active async session factory, initializing it if necessary."""
    if _session_factory is None:
        init_db()
        assert _session_factory is not None
    return _session_factory


@asynccontextmanager
async def get_db_transaction(
    user_id: str | None = None,
) -> AsyncIterator[AsyncSession]:
    """Async context manager providing a database session wrapped in a single transaction.

    Features:
    - Borrows a pooled connection without re-creating engine/connections per request.
    - Exactly one transaction per tool call (auto-commits on exit, auto-rolls back on error).
    - Sets transaction-local `app.current_user_id` via `set_config(..., true)`.
    """
    factory = get_session_factory()
    effective_user_id = user_id or get_current_user_id()

    async with factory() as session:
        async with session.begin():
            # Transaction-local parameter setting for RLS enforcement
            await session.execute(
                text("SELECT set_config('app.current_user_id', :uid, true)"),
                {"uid": effective_user_id},
            )
            yield session
