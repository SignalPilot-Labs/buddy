"""Tests for _post secret-scrubbing in sandbox_client.handlers.repo.

Verifies that RuntimeError messages raised by Repo._post never contain raw
secret values that were sent in the request body, even when the sandbox echoes
them verbatim in its error response body.

Uses httpx.MockTransport (respx not available in this environment).
"""

import json

import httpx
import pytest

from sandbox_client.handlers.repo import Repo


def _make_client(responses: list[httpx.Response]) -> httpx.AsyncClient:
    """Build an AsyncClient backed by a MockTransport that serves `responses` in order."""
    call_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_index
        resp = responses[call_index]
        call_index += 1
        return resp

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://sandbox")


class TestPostErrorRedaction:
    """Repo._post must scrub known-secret body keys from RuntimeError messages."""

    @pytest.mark.asyncio
    async def test_git_token_scrubbed_when_echoed_in_error_body(self) -> None:
        """500 body echoing the git PAT must not appear in the raised RuntimeError."""
        sentinel = "GHP_SENTINEL_GIT_TOKEN_123"
        body_text = json.dumps(
            {
                "detail": (
                    f"git clone failed: "
                    f"https://x-access-token:{sentinel}@github.com/owner/name.git"
                )
            }
        )
        client = _make_client(
            [httpx.Response(status_code=500, text=body_text)]
        )
        repo = Repo(client)

        with pytest.raises(RuntimeError) as exc_info:
            await repo.bootstrap(
                repo="owner/name",
                token=sentinel,
                base_branch="main",
                working_branch="wb",
                timeout=60,
            )

        msg = exc_info.value.args[0]
        assert sentinel not in msg
        assert "***REDACTED***" in msg
        assert "sandbox /repo/bootstrap -> 500" in msg

    @pytest.mark.asyncio
    async def test_claude_token_key_scrubbed(self) -> None:
        """claude_token in body must be scrubbed; non-secret values pass through."""
        sentinel = "sk-ant-SENTINEL_CLAUDE_456"
        body_text = json.dumps(
            {"detail": f"bad request: claude_token={sentinel} other=x"}
        )
        client = _make_client(
            [httpx.Response(status_code=422, text=body_text)]
        )
        repo = Repo(client)

        with pytest.raises(RuntimeError) as exc_info:
            await repo._post(
                "/repo/bootstrap",
                {"claude_token": sentinel, "other": "x"},
            )

        msg = exc_info.value.args[0]
        assert sentinel not in msg
        assert "***REDACTED***" in msg
        assert "x" in msg

    @pytest.mark.asyncio
    async def test_happy_path_returns_json_unchanged(self) -> None:
        """Success response (< 400) must not be touched by the scrub path."""
        payload = {"committed": True, "pushed": True, "push_error": None}
        client = _make_client(
            [httpx.Response(status_code=200, json=payload)]
        )
        repo = Repo(client)

        result = await repo.save("round message", 60)

        assert result.committed is True
        assert result.pushed is True
        assert result.push_error is None

    @pytest.mark.asyncio
    async def test_no_secret_keys_in_body_no_redaction_marker(self) -> None:
        """Error body with no secrets must be passed through without the REDACTED marker."""
        error_body = '{"detail": "diff failed: working tree not clean"}'
        client = _make_client(
            [httpx.Response(status_code=500, text=error_body)]
        )
        repo = Repo(client)

        with pytest.raises(RuntimeError) as exc_info:
            await repo.diff()

        msg = exc_info.value.args[0]
        assert "working tree not clean" in msg
        assert "***REDACTED***" not in msg
