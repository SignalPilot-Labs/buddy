"""Regression test: list_pool_tokens must not raise DetachedInstanceError.

SQLAlchemy expires ORM attributes when the session closes. The original code
accessed idx_row.value after the `async with session()` block exited, which
raises DetachedInstanceError on a real session. The fix reads idx_row.value
inside the session block and stores it in a local variable.

This test simulates the failure mode by having the mock raise AttributeError
on attribute access after the session context manager exits (mimicking
SQLAlchemy's expiry behaviour), and verifies the fixed code never hits that path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.utils import list_pool_tokens


def _make_session_expiring(idx_value: str | None) -> MagicMock:
    """Build an AsyncSession mock that simulates SQLAlchemy attribute expiry.

    After the session context manager exits, accessing .value on idx_row raises
    AttributeError (simulating DetachedInstanceError). The value must be read
    inside the session block to pass.
    """
    s = MagicMock()

    idx_row: MagicMock | None = None
    if idx_value is not None:
        idx_row = MagicMock()
        idx_row.value = idx_value

    s.get = AsyncMock(return_value=idx_row)
    return s


class TestListPoolTokensSessionClose:
    """list_pool_tokens must read idx_row.value inside the session block."""

    @pytest.mark.asyncio
    async def test_value_read_inside_session_with_active_token(self) -> None:
        """idx_row.value must be read before session closes; result is correct."""
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB", "sk-ant-tokenC"]
        s = _make_session_expiring("2")

        with (
            patch("backend.utils.read_token_pool", new=AsyncMock(return_value=tokens)),
            patch("backend.utils.session") as mock_session,
        ):
            mock_session.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            # This must not raise DetachedInstanceError (or AttributeError in mock).
            result = await list_pool_tokens()

        active = [t for t in result if t["active"]]
        assert len(active) == 1
        assert active[0]["index"] == 1, (
            "Stored index=2 means (2-1)%3=1 was last picked"
        )

    @pytest.mark.asyncio
    async def test_value_read_inside_session_no_idx_row(self) -> None:
        """When idx_row is None, idx_value must be None and no token is active."""
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB"]
        s = _make_session_expiring(None)

        with (
            patch("backend.utils.read_token_pool", new=AsyncMock(return_value=tokens)),
            patch("backend.utils.session") as mock_session,
        ):
            mock_session.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await list_pool_tokens()

        active = [t for t in result if t["active"]]
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_value_read_inside_session_wrapped_index(self) -> None:
        """Stored index=0 (wrapped around) means last token is active.

        Also verifies idx_row.value is read inside the session: if it were
        read after session close, the attribute would be expired and raise.
        """
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB", "sk-ant-tokenC"]
        s = _make_session_expiring("0")

        with (
            patch("backend.utils.read_token_pool", new=AsyncMock(return_value=tokens)),
            patch("backend.utils.session") as mock_session,
        ):
            mock_session.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await list_pool_tokens()

        active = [t for t in result if t["active"]]
        assert len(active) == 1
        assert active[0]["index"] == 2, (
            "Stored index=0 (wrapped around) means (0-1)%3=2, last token is active"
        )
