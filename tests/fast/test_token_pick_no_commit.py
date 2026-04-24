"""Regression test for _pick_next_claude_token committing the session internally.

Bug: _pick_next_claude_token called await s.commit() before returning.
This committed the transaction before read_credentials had finished reading
env_vars and host_mounts. If those later reads raised an error, the index
advance was already durably committed, causing token skew on retries.

Fix: Remove s.commit() from _pick_next_claude_token; add it in read_credentials
after the token is picked and only when a token was actually returned.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.utils import _pick_next_claude_token


def _make_session(idx_value: str | None, tokens: list[str]) -> MagicMock:
    """Build an AsyncSession mock with the given idx and token list."""
    s = MagicMock()

    idx_row: MagicMock | None = None
    if idx_value is not None:
        idx_row = MagicMock()
        idx_row.value = idx_value

    s.get = AsyncMock(return_value=idx_row)
    s.commit = AsyncMock()
    return s


class TestTokenPickNoCommit:
    """_pick_next_claude_token must NOT commit the session internally."""

    @pytest.mark.asyncio
    async def test_commit_not_called_on_pick(self) -> None:
        """_pick_next_claude_token must not call s.commit()."""
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB"]
        s = _make_session("0", tokens)

        with patch("backend.utils.read_token_pool", new=AsyncMock(return_value=tokens)):
            with patch("backend.utils.upsert_setting", new=AsyncMock()):
                result = await _pick_next_claude_token(s)

        assert result == "sk-ant-tokenA"
        s.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_setting_still_called(self) -> None:
        """_pick_next_claude_token must still call upsert_setting to advance the index."""
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB", "sk-ant-tokenC"]
        s = _make_session("1", tokens)

        with patch("backend.utils.read_token_pool", new=AsyncMock(return_value=tokens)):
            with patch("backend.utils.upsert_setting", new=AsyncMock()) as mock_upsert:
                result = await _pick_next_claude_token(s)

        assert result == "sk-ant-tokenB"
        mock_upsert.assert_called_once()
        # Verify the index is advanced to 2 (next after index 1)
        call_args = mock_upsert.call_args
        assert call_args[0][1] == "claude_token_index"
        assert call_args[0][2] == "2"

    @pytest.mark.asyncio
    async def test_empty_pool_returns_none_without_commit(self) -> None:
        """With an empty token pool, returns None and does not commit."""
        s = _make_session(None, [])

        with patch("backend.utils.read_token_pool", new=AsyncMock(return_value=[])):
            result = await _pick_next_claude_token(s)

        assert result is None
        s.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_wraps_around(self) -> None:
        """Index wraps to 0 after the last token and commit is not called."""
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB"]
        s = _make_session("1", tokens)  # last index, picks tokenB, next = 0

        with patch("backend.utils.read_token_pool", new=AsyncMock(return_value=tokens)):
            with patch("backend.utils.upsert_setting", new=AsyncMock()) as mock_upsert:
                result = await _pick_next_claude_token(s)

        assert result == "sk-ant-tokenB"
        s.commit.assert_not_called()
        call_args = mock_upsert.call_args
        assert call_args[0][2] == "0"  # wrapped back to 0
