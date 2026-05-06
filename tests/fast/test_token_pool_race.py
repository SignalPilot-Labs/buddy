"""Regression test for token pool read-modify-write race condition.

Bug: add_token_to_pool, remove_token_from_pool, and _pick_next_claude_token
all follow a read-modify-write pattern without database-level locking.
Concurrent calls could interleave reads and writes, losing updates or
making conflicting decisions on stale state.

Fix: read_token_pool() accepts for_update=True which issues SELECT...FOR UPDATE,
holding a row-level lock for the duration of the transaction. All callers
that modify the pool pass for_update=True.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()

from backend.utils import (
    _pick_next_claude_token,
    add_token_to_pool,
    list_pool_tokens,
    read_token_pool,
    remove_token_from_pool,
)


def _make_session_with_pool(tokens: list[str], encrypted_blob: str = "enc-blob") -> MagicMock:
    """Build an AsyncSession mock that returns a pool setting with given tokens."""
    pool_row = MagicMock()
    pool_row.value = encrypted_blob

    s = MagicMock()
    s.get = AsyncMock(return_value=pool_row)
    s.execute = AsyncMock()
    s.commit = AsyncMock()
    return s


class TestReadTokenPoolForUpdate:
    """read_token_pool must use SELECT...FOR UPDATE when for_update=True."""

    @pytest.mark.asyncio
    async def test_for_update_false_uses_session_get(self) -> None:
        """Without for_update, read_token_pool uses s.get() (no lock)."""
        tokens = ["tok-1"]
        s = MagicMock()
        pool_row = MagicMock()
        pool_row.value = "enc"
        s.get = AsyncMock(return_value=pool_row)

        with patch("backend.utils.crypto") as mock_crypto:
            mock_crypto.decrypt.return_value = json.dumps(tokens)
            await read_token_pool(s, for_update=False)

        s.get.assert_called_once()
        s.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_for_update_true_uses_execute_with_for_update(self) -> None:
        """With for_update=True, read_token_pool must call s.execute (not s.get)."""
        tokens = ["tok-1"]
        s = MagicMock()
        pool_row = MagicMock()
        pool_row.value = "enc"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pool_row
        s.execute = AsyncMock(return_value=result_mock)

        with patch("backend.utils.crypto") as mock_crypto:
            mock_crypto.decrypt.return_value = json.dumps(tokens)
            result = await read_token_pool(s, for_update=True)

        s.get.assert_not_called()
        s.execute.assert_called_once()
        assert result == tokens

    @pytest.mark.asyncio
    async def test_for_update_true_returns_empty_when_no_row(self) -> None:
        """With for_update=True and no pool row, must return empty list."""
        s = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        s.execute = AsyncMock(return_value=result_mock)

        result = await read_token_pool(s, for_update=True)

        assert result == []


class TestAddTokenToPoolUsesLock:
    """add_token_to_pool must call read_token_pool with for_update=True."""

    @pytest.mark.asyncio
    async def test_add_calls_read_with_for_update(self) -> None:
        """add_token_to_pool must pass for_update=True to read_token_pool."""
        captured_kwargs: list[dict] = []

        async def fake_read_token_pool(s: MagicMock, for_update: bool = False) -> list[str]:
            captured_kwargs.append({"for_update": for_update})
            return ["existing-token"]

        s = MagicMock()
        s.commit = AsyncMock()

        with (
            patch("backend.utils.read_token_pool", new=fake_read_token_pool),
            patch("backend.utils._write_token_pool", new=AsyncMock()),
            patch("backend.utils.session") as mock_session_ctx,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            await add_token_to_pool("new-token")

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["for_update"] is True

    @pytest.mark.asyncio
    async def test_list_pool_tokens_does_not_use_for_update(self) -> None:
        """list_pool_tokens is read-only and must NOT pass for_update=True."""
        captured_kwargs: list[dict] = []

        async def fake_read_token_pool(s: MagicMock, for_update: bool = False) -> list[str]:
            captured_kwargs.append({"for_update": for_update})
            return []

        s = MagicMock()
        s.get = AsyncMock(return_value=None)

        with (
            patch("backend.utils.read_token_pool", new=fake_read_token_pool),
            patch("backend.utils.session") as mock_session_ctx,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            await list_pool_tokens()

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["for_update"] is False


class TestRemoveTokenFromPoolUsesLock:
    """remove_token_from_pool must call read_token_pool with for_update=True."""

    @pytest.mark.asyncio
    async def test_remove_calls_read_with_for_update(self) -> None:
        """remove_token_from_pool must pass for_update=True to read_token_pool."""
        captured_kwargs: list[dict] = []

        async def fake_read_token_pool(s: MagicMock, for_update: bool = False) -> list[str]:
            captured_kwargs.append({"for_update": for_update})
            return ["token-a", "token-b"]

        s = MagicMock()
        s.get = AsyncMock(return_value=None)
        s.commit = AsyncMock()

        with (
            patch("backend.utils.read_token_pool", new=fake_read_token_pool),
            patch("backend.utils._write_token_pool", new=AsyncMock()),
            patch("backend.utils.session") as mock_session_ctx,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            await remove_token_from_pool(0)

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["for_update"] is True

    @pytest.mark.asyncio
    async def test_remove_out_of_range_raises_value_error(self) -> None:
        """Removing an out-of-range index must raise ValueError."""
        s = MagicMock()
        s.commit = AsyncMock()

        with (
            patch("backend.utils.read_token_pool", new=AsyncMock(return_value=["only-token"])),
            patch("backend.utils.session") as mock_session_ctx,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            with pytest.raises(ValueError, match="out of range"):
                await remove_token_from_pool(5)


class TestPickNextTokenUsesLock:
    """_pick_next_claude_token must call read_token_pool with for_update=True."""

    @pytest.mark.asyncio
    async def test_pick_calls_read_with_for_update(self) -> None:
        """_pick_next_claude_token must pass for_update=True to read_token_pool."""
        captured_kwargs: list[dict] = []

        async def fake_read_token_pool(s: MagicMock, for_update: bool = False) -> list[str]:
            captured_kwargs.append({"for_update": for_update})
            return ["tok-1", "tok-2"]

        s = MagicMock()
        idx_row = MagicMock()
        idx_row.value = "0"
        s.get = AsyncMock(return_value=idx_row)

        with (
            patch("backend.utils.read_token_pool", new=fake_read_token_pool),
            patch("backend.utils.upsert_setting", new=AsyncMock()),
        ):
            result = await _pick_next_claude_token(s)

        assert result == "tok-1"
        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["for_update"] is True
