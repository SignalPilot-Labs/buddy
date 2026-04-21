"""Tests for sandbox _post_to_agent retry logic.

Verifies:
- Successful POST on first attempt returns immediately
- 5xx triggers retry, succeeds on second attempt
- Timeout triggers retry
- 4xx does NOT retry (client error)
- All retries exhausted logs warning but does not raise
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sandbox.session.utils as utils_module


class _FakeResponse:
    """Minimal async context manager mimicking aiohttp response."""

    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


def _patch_client(side_effects: list) -> MagicMock:
    """Build a mock client whose .post() returns responses or raises in order."""
    client = MagicMock()
    client.post = MagicMock(side_effect=side_effects)
    return client


class TestPostToAgentRetry:
    """_post_to_agent retries on 5xx and transient errors."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        client = _patch_client([_FakeResponse(200)])
        with (
            patch.object(utils_module, "_get_agent_client", return_value=client),
            patch.object(utils_module, "_AGENT_URL", "http://agent:8500"),
            patch.object(utils_module, "_SANDBOX_SECRET", "secret"),
        ):
            await utils_module._post_to_agent("/internal/test", {"key": "val"})
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_500(self) -> None:
        client = _patch_client([_FakeResponse(500), _FakeResponse(200)])
        with (
            patch.object(utils_module, "_get_agent_client", return_value=client),
            patch.object(utils_module, "_AGENT_URL", "http://agent:8500"),
            patch.object(utils_module, "_SANDBOX_SECRET", "secret"),
            patch("sandbox.session.utils.asyncio.sleep", new_callable=AsyncMock),
        ):
            await utils_module._post_to_agent("/internal/test", {})
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self) -> None:
        import asyncio
        client = _patch_client([asyncio.TimeoutError(), _FakeResponse(200)])
        with (
            patch.object(utils_module, "_get_agent_client", return_value=client),
            patch.object(utils_module, "_AGENT_URL", "http://agent:8500"),
            patch.object(utils_module, "_SANDBOX_SECRET", "secret"),
            patch("sandbox.session.utils.asyncio.sleep", new_callable=AsyncMock),
        ):
            await utils_module._post_to_agent("/internal/test", {})
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self) -> None:
        client = _patch_client([_FakeResponse(400)])
        with (
            patch.object(utils_module, "_get_agent_client", return_value=client),
            patch.object(utils_module, "_AGENT_URL", "http://agent:8500"),
            patch.object(utils_module, "_SANDBOX_SECRET", "secret"),
        ):
            await utils_module._post_to_agent("/internal/test", {})
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_does_not_raise(self) -> None:
        client = _patch_client([_FakeResponse(500), _FakeResponse(500), _FakeResponse(500)])
        with (
            patch.object(utils_module, "_get_agent_client", return_value=client),
            patch.object(utils_module, "_AGENT_URL", "http://agent:8500"),
            patch.object(utils_module, "_SANDBOX_SECRET", "secret"),
            patch("sandbox.session.utils.asyncio.sleep", new_callable=AsyncMock),
        ):
            # Must not raise — logs warning and returns
            await utils_module._post_to_agent("/internal/test", {})
        assert client.post.call_count == 3
