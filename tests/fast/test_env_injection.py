"""Unit test for environment variable injection into sandbox via POST /env.

Verifies that SandboxClient.env.set() posts the correct payload to the
sandbox /env endpoint. This is the universal injection path used by all
sandbox types (local Docker, remote Docker, Slurm) after creation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sandbox_client.handlers.env import Env


def _make_handler() -> tuple[Env, AsyncMock]:
    """Build an Env handler with a mocked HTTP client."""
    mock_http = MagicMock()
    mock_post = AsyncMock(return_value=MagicMock(status_code=200))
    mock_post.return_value.raise_for_status = MagicMock()
    mock_http.post = mock_post
    handler = Env.__new__(Env)
    handler._http = mock_http
    return handler, mock_post


class TestEnvInjection:
    """EnvHandler.set() must POST env vars to /env endpoint."""

    @pytest.mark.asyncio
    async def test_env_vars_posted_to_sandbox(self) -> None:
        """Non-empty env dict is posted as JSON to /env."""
        handler, mock_post = _make_handler()
        env = {"API_KEY": "secret123", "DB_URL": "postgres://..."}

        await handler.set(env)

        mock_post.assert_called_once_with("/env", json={"env_vars": env})

    @pytest.mark.asyncio
    async def test_empty_env_posted_to_sandbox(self) -> None:
        """Empty env dict is still posted (clears any stale vars)."""
        handler, mock_post = _make_handler()

        await handler.set({})

        mock_post.assert_called_once_with("/env", json={"env_vars": {}})

    @pytest.mark.asyncio
    async def test_env_keys_preserved_exactly(self) -> None:
        """Env var keys and values are not modified during injection."""
        handler, mock_post = _make_handler()
        env = {"SPECIAL_KEY_123": "value with spaces", "EMPTY_VAL": ""}

        await handler.set(env)

        posted = mock_post.call_args[1]["json"]["env_vars"]
        assert posted == env
