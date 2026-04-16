"""Tests for credential scrubbing in the agent /logs endpoint.

Monkeypatches pool().get_self_logs to return lines containing credential
strings, then asserts the endpoint response never leaks raw tokens.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from endpoints import register_routes

_CLAUDE_KEY = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_GITHUB_PAT = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890"
_API_KEY_HDR = "X-API-Key: rawsupersecretapikey1234567890"
_INTERNAL_SEC = "AGENT_INTERNAL_SECRET=mysecrettoken9876543210abcdef"
_DASHBOARD_KEY = "[dashboard] API key: AAAAAAAABBBBBBBBCCCCCCCC"


@pytest.fixture
def client() -> TestClient:
    """FastAPI app with agent routes and mocked pool returning credential lines."""
    app = FastAPI()

    mock_pool = MagicMock()
    mock_pool.get_self_logs = AsyncMock(
        return_value=[
            "[abc12345] Round 1 begin",
            f"token in use: {_CLAUDE_KEY}",
            f"git token: {_GITHUB_PAT}",
            _API_KEY_HDR,
            _INTERNAL_SEC,
            _DASHBOARD_KEY,
            "normal log line — no secrets",
        ]
    )
    mock_pool.get_client.return_value = None

    server = MagicMock()
    server.pool.return_value = mock_pool

    register_routes(app, server)
    return TestClient(app)


class TestAgentLogsEndpointScrub:
    """The /logs endpoint must scrub all credential-like tokens from its response."""

    def test_claude_key_not_in_response(self, client: TestClient) -> None:
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        body = "\n".join(res.json()["lines"])
        assert "sk-ant-" not in body

    def test_github_pat_not_in_response(self, client: TestClient) -> None:
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        body = "\n".join(res.json()["lines"])
        assert "ghp_" not in body

    def test_api_key_header_value_not_in_response(self, client: TestClient) -> None:
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        body = "\n".join(res.json()["lines"])
        assert "rawsupersecretapikey1234567890" not in body

    def test_agent_internal_secret_not_in_response(self, client: TestClient) -> None:
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        body = "\n".join(res.json()["lines"])
        assert "mysecrettoken9876543210abcdef" not in body

    def test_dashboard_key_not_in_response(self, client: TestClient) -> None:
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        body = "\n".join(res.json()["lines"])
        assert "AAAAAAAABBBBBBBBCCCCCCCC" not in body

    def test_redacted_marker_present(self, client: TestClient) -> None:
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        body = "\n".join(res.json()["lines"])
        assert "[REDACTED]" in body

    def test_clean_lines_preserved(self, client: TestClient) -> None:
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        lines = res.json()["lines"]
        assert any("normal log line" in line for line in lines)

    def test_line_count_preserved(self, client: TestClient) -> None:
        """Scrubbing must not drop lines — only replace values."""
        res = client.get("/logs", params={"tail": 100})
        assert res.status_code == 200
        assert res.json()["total"] == 7
