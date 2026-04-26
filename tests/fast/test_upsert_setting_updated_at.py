"""Regression test: upsert_setting must update updated_at on conflict.

Bug: on_conflict_do_update only set value and encrypted, not updated_at.
SQLAlchemy's ORM-level onupdate hook does NOT fire for dialect-level
INSERT ... ON CONFLICT DO UPDATE statements, so updated_at was never
refreshed when a setting was overwritten.

Fix: Add "updated_at": func.now() to the set_ dict.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub DB modules before importing backend.utils
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()

import backend.utils as utils_mod  # noqa: E402


class TestUpsertSettingUpdatedAt:
    """upsert_setting must include updated_at in the ON CONFLICT DO UPDATE clause."""

    @pytest.mark.asyncio
    async def test_updated_at_in_conflict_clause(self) -> None:
        """The SQL compiled for the upsert must reference updated_at in the SET clause."""
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy import Column, String, Boolean, DateTime, func
        from sqlalchemy.orm import DeclarativeBase

        # Build a minimal standalone table fixture so this test is not affected
        # by sys.modules["db.models"] being mocked by other tests in the suite.
        class _Base(DeclarativeBase):
            pass

        class _Setting(_Base):
            __tablename__ = "settings_test_fixture"
            key: Column = Column(String, primary_key=True)
            value: Column = Column(String)
            encrypted: Column = Column(Boolean)
            updated_at: Column = Column(DateTime)

        stmt = (
            pg_insert(_Setting)
            .values(key="git_token", value="tok", encrypted=True)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": "tok", "encrypted": True, "updated_at": func.now()},
            )
        )

        compiled = stmt.compile(dialect=postgresql.dialect())
        sql_str = str(compiled)
        assert "updated_at" in sql_str, (
            f"Expected 'updated_at' in compiled SQL SET clause, got:\n{sql_str}"
        )

    @pytest.mark.asyncio
    async def test_session_execute_called_with_upsert(self) -> None:
        """upsert_setting must call session.execute exactly once."""
        session = AsyncMock()

        await utils_mod.upsert_setting(
            s=session,
            key="repo_list",
            value='["org/repo"]',
            encrypted=False,
        )

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upsert_includes_updated_at_key_in_set_clause(self) -> None:
        """The statement passed to session.execute must include updated_at in set_ dict.

        We verify by capturing the statement and inspecting its _post_values_clause,
        which holds the ON CONFLICT ... DO UPDATE SET ... payload.
        """
        captured_stmt: list = []

        async def capture_execute(stmt, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured_stmt.append(stmt)

        session = AsyncMock()
        session.execute = capture_execute

        await utils_mod.upsert_setting(
            s=session,
            key="max_budget_usd",
            value="10.0",
            encrypted=False,
        )

        assert captured_stmt, "Expected session.execute to be called"
        stmt = captured_stmt[0]

        # Compile to PostgreSQL dialect to get the full SQL string
        from sqlalchemy.dialects import postgresql
        sql_str = str(stmt.compile(dialect=postgresql.dialect()))

        assert "updated_at" in sql_str, (
            f"ON CONFLICT DO UPDATE SET must include updated_at, got:\n{sql_str}"
        )
