"""Verify /branches and /diff/repo require X-GitHub-Token header and reject query-param tokens.

Regression test for PR #153: the token must travel in a request header, not in
the query string (which gets written to uvicorn access logs in plain text).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from endpoints import register_routes


@pytest.fixture
def client() -> TestClient:
    """FastAPI app with agent routes wired to a mock server."""
    app = FastAPI()
    server = MagicMock()
    # /diff/repo: no active sandbox client → falls through to GitHub API path.
    server.pool.return_value.get_client.return_value = None
    register_routes(app, server)
    return TestClient(app)


class TestBranchesHeaderAuth:
    """/branches must accept token via X-GitHub-Token header and reject query param."""

    def test_missing_header_returns_422(self, client: TestClient) -> None:
        res = client.get("/branches", params={"repo": "owner/name"})
        assert res.status_code == 422

    def test_token_in_query_param_is_ignored(self, client: TestClient) -> None:
        # Previously the endpoint accepted ?token=...; it must no longer.
        res = client.get("/branches", params={"repo": "owner/name", "token": "ghp_leak"})
        assert res.status_code == 422

    def test_header_accepted(self, client: TestClient) -> None:
        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = [{"name": "main"}]
        with patch("endpoints.httpx.AsyncClient") as mock_cls:
            ctx = mock_cls.return_value.__aenter__.return_value
            async def _get(*args, **kwargs):
                return fake
            ctx.get.side_effect = _get
            res = client.get(
                "/branches",
                params={"repo": "owner/name"},
                headers={"X-GitHub-Token": "ghp_abc"},
            )
        assert res.status_code == 200


class TestDiffRepoHeaderAuth:
    """/diff/repo must accept token via X-GitHub-Token header and reject query param."""

    _PARAMS = {"run_id": "r1", "branch": "feature", "base": "main", "repo": "owner/name"}

    def test_missing_header_returns_422(self, client: TestClient) -> None:
        res = client.get("/diff/repo", params=self._PARAMS)
        assert res.status_code == 422

    def test_token_in_query_param_is_ignored(self, client: TestClient) -> None:
        res = client.get("/diff/repo", params={**self._PARAMS, "token": "ghp_leak"})
        assert res.status_code == 422

    def test_header_accepted(self, client: TestClient) -> None:
        async def _fake_fetch(repo, branch, base, token):
            assert token == "ghp_abc"
            return {"diff": "diff --git a/x b/x"}

        with patch("endpoints.fetch_github_diff", side_effect=_fake_fetch):
            res = client.get(
                "/diff/repo",
                params=self._PARAMS,
                headers={"X-GitHub-Token": "ghp_abc"},
            )
        assert res.status_code == 200
        assert "diff" in res.json()
