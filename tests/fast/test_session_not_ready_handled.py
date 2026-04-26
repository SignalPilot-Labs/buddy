"""Regression test: 503 ClientNotReadyError does not kill the round.

Previously, a 503 from the sandbox on send_message/interrupt propagated as
httpx.HTTPStatusError through the runner and terminated the round with
status='error'. Now the agent-side sandbox client raises SessionNotReadyError
which the runner catches gracefully.
"""

from unittest.mock import AsyncMock

import httpx
import pytest

from sandbox_client.handlers.session import Session, SessionNotReadyError

HTTP_503 = 503
HTTP_200 = 200
HTTP_500 = 500


class TestSandboxClientSessionNotReady:
    """Agent-side sandbox client must raise SessionNotReadyError on 503."""

    @pytest.mark.asyncio
    async def test_send_message_503_raises_session_not_ready(self) -> None:
        """send_message receiving 503 must raise SessionNotReadyError, not HTTPStatusError."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=httpx.Response(
            HTTP_503,
            json={"error": "client not ready"},
            request=httpx.Request("POST", "http://sandbox:8080/session/abc/message"),
        ))
        session = Session(mock_http)

        with pytest.raises(SessionNotReadyError, match="not ready"):
            await session.send_message("abc123", "hello")

    @pytest.mark.asyncio
    async def test_interrupt_503_raises_session_not_ready(self) -> None:
        """interrupt receiving 503 must raise SessionNotReadyError, not HTTPStatusError."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=httpx.Response(
            HTTP_503,
            json={"error": "client not ready"},
            request=httpx.Request("POST", "http://sandbox:8080/session/abc/interrupt"),
        ))
        session = Session(mock_http)

        with pytest.raises(SessionNotReadyError, match="not ready"):
            await session.interrupt("abc123")

    @pytest.mark.asyncio
    async def test_send_message_200_succeeds(self) -> None:
        """send_message receiving 200 must not raise."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=httpx.Response(
            HTTP_200,
            json={"status": "sent"},
            request=httpx.Request("POST", "http://sandbox:8080/session/abc/message"),
        ))
        session = Session(mock_http)

        await session.send_message("abc123", "hello")

    @pytest.mark.asyncio
    async def test_send_message_500_raises_http_error(self) -> None:
        """send_message receiving 500 must still raise HTTPStatusError."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=httpx.Response(
            HTTP_500,
            json={"error": "internal"},
            request=httpx.Request("POST", "http://sandbox:8080/session/abc/message"),
        ))
        session = Session(mock_http)

        with pytest.raises(httpx.HTTPStatusError):
            await session.send_message("abc123", "hello")
