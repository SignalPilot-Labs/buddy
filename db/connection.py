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
        await _migrate_cache_token_columns(conn)
        await _migrate_context_tokens_column(conn)
        await _migrate_model_name_column(conn)
        await _migrate_branch_name_nullable(conn)


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


async def _migrate_cache_token_columns(conn) -> None:
    """Add cache token columns to runs table if they don't exist."""
    for col in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        result = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'runs' AND column_name = :col"
        ), {"col": col})
        if result.first() is None:
            await conn.execute(text(
                f"ALTER TABLE runs ADD COLUMN {col} INTEGER DEFAULT 0"
            ))
            log.info("Added column runs.%s", col)


async def _migrate_context_tokens_column(conn) -> None:
    """Add context_tokens column to runs table if it doesn't exist."""
    result = await conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'runs' AND column_name = 'context_tokens'"
    ))
    if result.first() is None:
        await conn.execute(text(
            "ALTER TABLE runs ADD COLUMN context_tokens INTEGER DEFAULT 0"
        ))
        log.info("Added column runs.context_tokens")


async def _migrate_model_name_column(conn) -> None:
    """Add model_name column to runs table if it doesn't exist."""
    result = await conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'runs' AND column_name = 'model_name'"
    ))
    if result.first() is None:
        await conn.execute(text(
            "ALTER TABLE runs ADD COLUMN model_name VARCHAR"
        ))
        log.info("Added column runs.model_name")


async def _migrate_branch_name_nullable(conn) -> None:
    """Make branch_name nullable and convert 'pending' placeholders to NULL.

    branch_name was NOT NULL with a 'pending' placeholder set before
    bootstrap assigned a real branch. The placeholder collides with any
    real branch of the same name on the remote. NULL is the correct
    representation for 'not yet assigned'.
    """
    result = await conn.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'runs' AND column_name = 'branch_name'"
    ))
    row = result.first()
    if row and row[0] == "NO":
        await conn.execute(text("ALTER TABLE runs ALTER COLUMN branch_name DROP NOT NULL"))
        await conn.execute(text("UPDATE runs SET branch_name = NULL WHERE branch_name = 'pending'"))
        log.info("Migrated runs.branch_name to nullable, converted 'pending' to NULL")


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
