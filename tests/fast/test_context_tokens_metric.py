"""Regression test: context tokens metric must not include output tokens.

Previously line 247 of stream.py computed:
    self._latest_context_tokens = inp + out + cache_create + cache_read

Output tokens are generated tokens, NOT part of the context window. The correct
formula is inp + cache_create + cache_read. Including output tokens inflated the
reported context size shown in the dashboard StatsBar.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.fast.conftest import _make_dispatcher


class TestContextTokensMetric:
    """StreamDispatcher._latest_context_tokens must exclude output tokens."""

    @pytest.mark.asyncio
    async def test_context_tokens_excludes_output_tokens(self) -> None:
        """_latest_context_tokens = inp + cache_create + cache_read (no output)."""
        dispatcher, _ = _make_dispatcher()

        inp = 1000
        out = 200
        cache_create = 50
        cache_read = 30

        with patch("agent_session.stream.log_audit", new=AsyncMock()):
            await dispatcher._accumulate_usage(
                {
                    "usage": {
                        "input_tokens": inp,
                        "output_tokens": out,
                        "cache_creation_input_tokens": cache_create,
                        "cache_read_input_tokens": cache_read,
                    }
                }
            )

        expected = inp + cache_create + cache_read
        assert dispatcher._latest_context_tokens == expected
        assert dispatcher._latest_context_tokens != inp + out + cache_create + cache_read

    @pytest.mark.asyncio
    async def test_context_tokens_zero_output_no_regression(self) -> None:
        """When output tokens are zero, result is same regardless of formula."""
        dispatcher, _ = _make_dispatcher()

        inp = 500
        cache_create = 10
        cache_read = 20

        with patch("agent_session.stream.log_audit", new=AsyncMock()):
            await dispatcher._accumulate_usage(
                {
                    "usage": {
                        "input_tokens": inp,
                        "output_tokens": 0,
                        "cache_creation_input_tokens": cache_create,
                        "cache_read_input_tokens": cache_read,
                    }
                }
            )

        assert dispatcher._latest_context_tokens == inp + cache_create + cache_read

    @pytest.mark.asyncio
    async def test_context_tokens_only_input(self) -> None:
        """Only input tokens, no cache, no output — context is just input."""
        dispatcher, _ = _make_dispatcher()

        with patch("agent_session.stream.log_audit", new=AsyncMock()):
            await dispatcher._accumulate_usage(
                {
                    "usage": {
                        "input_tokens": 800,
                        "output_tokens": 400,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    }
                }
            )

        assert dispatcher._latest_context_tokens == 800
