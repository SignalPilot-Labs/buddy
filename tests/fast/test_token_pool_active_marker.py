"""Regression test for token pool active marker off-by-one.

Previously list_pool_tokens used `current_idx % len(tokens)` as the active
index. But _pick_next_claude_token stores (idx + 1) after picking, so the
stored index always points to the NEXT token, not the last-picked one.
The fix uses `(current_idx - 1) % len(tokens)` to point back to last-picked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.utils import list_pool_tokens


def _make_session(idx_value: str | None, tokens: list[str]) -> MagicMock:
    """Build an AsyncSession mock that returns the given idx and token pool."""
    s = MagicMock()

    idx_row: MagicMock | None = None
    if idx_value is not None:
        idx_row = MagicMock()
        idx_row.value = idx_value

    s.get = AsyncMock(return_value=idx_row)
    return s


class TestTokenPoolActiveMarker:
    """list_pool_tokens must mark the last-picked token, not the next-to-pick."""

    @pytest.mark.asyncio
    async def test_active_is_last_picked_not_next(self) -> None:
        """With 3 tokens and stored index=1, token at index 0 must be active."""
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB", "sk-ant-tokenC"]
        s = _make_session("1", tokens)

        with (
            patch("backend.utils.read_token_pool", new=AsyncMock(return_value=tokens)),
            patch("backend.utils.session") as mock_session,
        ):
            mock_session.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await list_pool_tokens()

        active = [t for t in result if t["active"]]
        assert len(active) == 1
        assert active[0]["index"] == 0, (
            "Token at index 0 must be active (last picked), not index 1 (next to pick)"
        )

    @pytest.mark.asyncio
    async def test_active_wraps_around_on_first_pick(self) -> None:
        """With stored index=0 (just wrapped around), last token must be active."""
        tokens = ["sk-ant-tokenA", "sk-ant-tokenB", "sk-ant-tokenC"]
        s = _make_session("0", tokens)

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
            "With stored index=0 (wrapped), the last token (index 2) must be active"
        )

    @pytest.mark.asyncio
    async def test_empty_pool_returns_empty_list(self) -> None:
        """Empty token pool must return empty list, not raise."""
        s = _make_session(None, [])

        with (
            patch("backend.utils.read_token_pool", new=AsyncMock(return_value=[])),
            patch("backend.utils.session") as mock_session,
        ):
            mock_session.return_value.__aenter__ = AsyncMock(return_value=s)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await list_pool_tokens()

        assert result == []
