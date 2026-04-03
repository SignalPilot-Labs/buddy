"""Async database connection with connection pooling via psycopg.

All connection parameters come from config/loader.py (config.yml + env overrides).
No hardcoded defaults here — config.yml is the single source of truth.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config.loader import database_config
from db.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_dsn(cfg: dict) -> str:
    """Build PostgreSQL DSN from config dict."""
    return "postgresql+psycopg://{user}:{password}@{host}:{port}/{name}".format(**cfg)


async def connect() -> async_sessionmaker[AsyncSession]:
    """Connect to the database and return a session factory."""
    global _engine, _session_factory

    cfg = database_config()
    _engine = create_async_engine(
        _build_dsn(cfg),
        pool_size=cfg["pool_size"],
        max_overflow=cfg["max_overflow"],
        pool_timeout=cfg["pool_timeout"],
        pool_recycle=cfg["pool_recycle"],
        echo=cfg["echo"],
    )

    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


async def create_tables() -> None:
    """Create all tables from ORM models. Only called by the db init process."""
    if _engine is None:
        raise RuntimeError("Not connected. Call connect() first.")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory. Raises if not initialized."""
    if _session_factory is None:
        raise RuntimeError("Not connected. Call connect() first.")
    return _session_factory


async def close() -> None:
    """Dispose of the engine and release all pooled connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
