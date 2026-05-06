"""Regression test for SSE token store race condition.

Verifies that concurrent token creation and validation with forced expiration
does not raise KeyError or RuntimeError when multiple coroutines prune
the same token simultaneously.
"""

import asyncio
import time
from unittest.mock import patch

from backend.sse_tokens import _tokens, create_sse_token, validate_sse_token


class TestSseTokenRace:
    """Concurrent SSE token operations must not raise on simultaneous deletion."""

    def setup_method(self) -> None:
        """Clear the token store before each test."""
        _tokens.clear()

    def teardown_method(self) -> None:
        """Clear the token store after each test."""
        _tokens.clear()

    def test_pop_is_idempotent_on_expired_token(self) -> None:
        """pop(tok, None) must not raise if another coroutine deleted the token first."""
        with patch("backend.sse_tokens.time.time", return_value=1000.0):
            token = create_sse_token()

        # Token is now expired (current time >> expiry)
        with patch("backend.sse_tokens.time.time", return_value=999999.0):
            # First validation removes the token
            result1 = validate_sse_token(token)
            # Second validation on the same (now absent) token must not raise KeyError
            result2 = validate_sse_token(token)

        assert result1 is False
        assert result2 is False

    def test_prune_does_not_raise_on_concurrent_deletion(self) -> None:
        """_prune_expired must not raise if a token was already removed by validate."""
        with patch("backend.sse_tokens.time.time", return_value=1000.0):
            token = create_sse_token()

        # Manually remove the token to simulate concurrent deletion
        _tokens.pop(token, None)

        # _prune_expired tries to delete the same (already deleted) token
        # With the old del _tokens[tok] this would raise KeyError
        with patch("backend.sse_tokens.time.time", return_value=999999.0):
            # create_sse_token internally calls _prune_expired
            second_token = create_sse_token()

        assert second_token != token
        assert second_token in _tokens

    def test_concurrent_validate_and_create_no_error(self) -> None:
        """Concurrent async calls to create and validate must not raise."""

        async def run_concurrent() -> None:
            with patch("backend.sse_tokens.time.time", return_value=1000.0):
                tokens = [create_sse_token() for _ in range(10)]

            # Expire all tokens
            async def validate_all() -> None:
                with patch("backend.sse_tokens.time.time", return_value=999999.0):
                    for tok in tokens:
                        validate_sse_token(tok)

            async def create_more() -> None:
                with patch("backend.sse_tokens.time.time", return_value=999999.0):
                    for _ in range(5):
                        create_sse_token()

            await asyncio.gather(validate_all(), create_more())

        asyncio.run(run_concurrent())

    def test_validate_valid_token_returns_true(self) -> None:
        """A non-expired token must validate successfully."""
        now = time.time()
        with patch("backend.sse_tokens.time.time", return_value=now):
            token = create_sse_token()

        with patch("backend.sse_tokens.time.time", return_value=now + 1):
            result = validate_sse_token(token)

        assert result is True

    def test_expired_token_returns_false_and_is_removed(self) -> None:
        """An expired token must return False and be removed from the store."""
        with patch("backend.sse_tokens.time.time", return_value=1000.0):
            token = create_sse_token()

        with patch("backend.sse_tokens.time.time", return_value=999999.0):
            result = validate_sse_token(token)

        assert result is False
        assert token not in _tokens
