"""Regression tests for ClientNotReadyError when send_message/interrupt called before client init.

When a session exists but Session.client is None (the SDK client has not yet
initialized), send_message and interrupt must raise ClientNotReadyError instead
of silently no-oping.
"""

from unittest.mock import MagicMock

import pytest

from sdk.errors import ClientNotReadyError
from sdk.manager import SessionManager


def _make_manager_with_session(session_id: str, client=None) -> SessionManager:
    """Insert a mock session with a given client state into a fresh SessionManager."""
    manager = SessionManager()
    mock_session = MagicMock()
    mock_session.client = client
    manager._sessions[session_id] = mock_session
    return manager


class TestClientNotReadyError:
    """Verify send_message and interrupt raise ClientNotReadyError when client is None."""

    @pytest.mark.asyncio
    async def test_send_message_raises_when_client_is_none(self) -> None:
        """send_message must raise ClientNotReadyError when s.client is None."""
        manager = _make_manager_with_session("abc123", client=None)
        with pytest.raises(ClientNotReadyError) as exc_info:
            await manager.send_message("abc123", "hello")
        assert exc_info.value.session_id == "abc123"

    @pytest.mark.asyncio
    async def test_interrupt_raises_when_client_is_none(self) -> None:
        """interrupt must raise ClientNotReadyError when s.client is None."""
        manager = _make_manager_with_session("abc123", client=None)
        with pytest.raises(ClientNotReadyError) as exc_info:
            await manager.interrupt("abc123")
        assert exc_info.value.session_id == "abc123"

    @pytest.mark.asyncio
    async def test_send_message_succeeds_when_client_is_ready(self) -> None:
        """send_message must call client.query when s.client is not None."""

        async def _async_query(text: str) -> None:
            return None

        mock_client = MagicMock()
        mock_client.query = _async_query
        manager = _make_manager_with_session("abc123", client=mock_client)
        # Must not raise
        await manager.send_message("abc123", "hello")

    @pytest.mark.asyncio
    async def test_interrupt_succeeds_when_client_is_ready(self) -> None:
        """interrupt must call client.interrupt when s.client is not None."""

        async def _async_interrupt() -> None:
            return None

        mock_client = MagicMock()
        mock_client.interrupt = _async_interrupt
        manager = _make_manager_with_session("abc123", client=mock_client)
        # Must not raise
        await manager.interrupt("abc123")
