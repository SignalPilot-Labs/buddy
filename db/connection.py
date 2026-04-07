"""Async database connection with connection pooling via psycopg.

All connection parameters come from config/loader.py (config.yml + env overrides).
No hardcoded defaults here — config.yml is the single source of truth.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config.loader import database_config
from db.models import Base

log = logging.getLogger("db.connection")

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


async def run_migrations() -> None:
    """Reconcile DB schema with ORM models on startup.

    SQLAlchemy's create_all won't alter existing constraints, so we handle
    known migrations here. Each migration is idempotent and safe to re-run.
    """
    if _engine is None:
        raise RuntimeError("Not connected. Call connect() first.")
    async with _engine.begin() as conn:
        await _migrate_control_signals_constraint(conn)


async def _migrate_control_signals_constraint(conn) -> None:
    """Ensure control_signals check constraint includes all valid signals."""
    expected = "('pause', 'resume', 'inject', 'stop', 'unlock', 'kill')"
    result = await conn.execute(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'ck_control_signals_signal'"
    ))
    row = result.first()
    if row is None:
        return
    if "'kill'" not in (row[0] or ""):
        await conn.execute(text("ALTER TABLE control_signals DROP CONSTRAINT ck_control_signals_signal"))
        await conn.execute(text(
            f"ALTER TABLE control_signals ADD CONSTRAINT ck_control_signals_signal "
            f"CHECK (signal IN {expected})"
        ))
        log.info("Migrated ck_control_signals_signal constraint")


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
