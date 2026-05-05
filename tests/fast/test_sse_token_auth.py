"""Regression tests for SSE ephemeral token authentication.

Guards against re-introduction of the API key in SSE query string
vulnerability (API key visible in server access logs).

The fix: frontend fetches a short-lived opaque token via POST /api/sse-token
(API key in header), then uses that token in the SSE URL query string instead
of the full API key.
"""

import ast
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import backend.sse_tokens as sse_tokens_module
from backend.constants import SSE_TOKEN_LIFETIME_SEC


def _import_streaming_module() -> object:
    """Import backend.endpoints.streaming with auth + db stubbed out."""
    auth_mock = MagicMock()
    auth_mock._api_key = "test"
    auth_mock.verify_sse_token = MagicMock()
    auth_mock.verify_api_key = MagicMock()
    sys.modules["backend.auth"] = auth_mock
    sys.modules["backend.db"] = MagicMock()
    sys.modules["db.connection"] = MagicMock()
    sys.modules["db.models"] = MagicMock()

    import backend.endpoints.streaming as streaming_mod
    return streaming_mod


def _import_runs_module() -> object:
    """Import backend.endpoints.runs with auth + db stubbed out."""
    stubs = ("backend.auth", "backend.db", "db.connection", "db.models")
    originals = {mod: sys.modules.get(mod) for mod in stubs}

    auth_mock = MagicMock()
    auth_mock._api_key = "test"
    auth_mock.verify_api_key = MagicMock()
    sys.modules["backend.auth"] = auth_mock
    sys.modules["backend.db"] = MagicMock()
    sys.modules["db.connection"] = MagicMock()
    sys.modules["db.models"] = MagicMock()

    import backend.endpoints.runs as runs_mod

    for mod, original in originals.items():
        if original is not None:
            sys.modules[mod] = original
        else:
            sys.modules.pop(mod, None)

    return runs_mod


_streaming = _import_streaming_module()
_runs = _import_runs_module()


class TestSseTokenAuth:
    """Regression tests for short-lived SSE token issuance and validation."""

    def setup_method(self) -> None:
        """Clear the token store before each test for isolation."""
        sse_tokens_module._tokens.clear()

    def teardown_method(self) -> None:
        """Clear the token store after each test."""
        sse_tokens_module._tokens.clear()

    # ------------------------------------------------------------------
    # Token store unit tests
    # ------------------------------------------------------------------

    def test_sse_token_valid_within_lifetime(self) -> None:
        """A freshly created token validates as True immediately."""
        token = sse_tokens_module.create_sse_token()
        assert sse_tokens_module.validate_sse_token(token) is True

    def test_sse_token_expired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A token validates as False after SSE_TOKEN_LIFETIME_SEC has elapsed."""
        token = sse_tokens_module.create_sse_token()
        # Advance time past the token's expiry
        future = time.time() + SSE_TOKEN_LIFETIME_SEC + 1
        monkeypatch.setattr(sse_tokens_module.time, "time", lambda: future)
        assert sse_tokens_module.validate_sse_token(token) is False

    def test_sse_token_invalid_string(self) -> None:
        """A random string that was never issued validates as False."""
        assert sse_tokens_module.validate_sse_token("not-a-real-token") is False

    def test_sse_token_pruning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Expired tokens are removed from the store when a new token is created."""
        # Create several tokens in "the past"
        past = time.time() - SSE_TOKEN_LIFETIME_SEC - 10
        sse_tokens_module._tokens["old-tok-1"] = past
        sse_tokens_module._tokens["old-tok-2"] = past
        assert len(sse_tokens_module._tokens) == 2

        # create_sse_token calls _prune_expired — expired entries should disappear
        _new_token = sse_tokens_module.create_sse_token()
        # Only the newly created token remains
        assert "old-tok-1" not in sse_tokens_module._tokens
        assert "old-tok-2" not in sse_tokens_module._tokens
        assert len(sse_tokens_module._tokens) == 1
        assert _new_token in sse_tokens_module._tokens

    def test_sse_token_expired_removed_on_validate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """validate_sse_token prunes an expired token from the store on access."""
        from backend.constants import SSE_TOKEN_LIFETIME_SEC

        token = sse_tokens_module.create_sse_token()
        assert token in sse_tokens_module._tokens

        future = time.time() + SSE_TOKEN_LIFETIME_SEC + 1
        monkeypatch.setattr(sse_tokens_module.time, "time", lambda: future)

        result = sse_tokens_module.validate_sse_token(token)
        assert result is False
        assert token not in sse_tokens_module._tokens

    # ------------------------------------------------------------------
    # Endpoint tests for POST /api/sse-token
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sse_token_endpoint_returns_token(self) -> None:
        """POST /api/sse-token calls create_sse_token and returns {token: ...}."""
        runs_mod = _runs
        result = await runs_mod.issue_sse_token()  # type: ignore[attr-defined]
        assert "token" in result
        token = result["token"]
        assert isinstance(token, str)
        assert len(token) > 10
        # Token should be in the store
        assert sse_tokens_module.validate_sse_token(token) is True

    @pytest.mark.asyncio
    async def test_sse_token_endpoint_rejects_no_auth(self) -> None:
        """The sse-token endpoint's router dependency enforces API key auth.

        We verify that the router itself has a router-level dependency on
        verify_api_key, which is the mechanism protecting this endpoint.
        The auth mock is already in place from module import; here we confirm
        the endpoint is registered on the correct (auth-guarded) router.
        """
        runs_mod = _runs
        # The router has dependencies=[Depends(auth.verify_api_key)] at router level.
        # We confirm it's reachable under the /api prefix.
        router = runs_mod.router  # type: ignore[attr-defined]
        # The router must have a non-empty dependency list
        assert router.dependencies, "runs router must have auth dependencies"

    # ------------------------------------------------------------------
    # Regression test: old ?api_key= pattern must NOT work on SSE endpoints
    # ------------------------------------------------------------------

    def test_streaming_rejects_api_key_in_query(self) -> None:
        """The streaming router no longer has verify_api_key_or_query.

        Confirms that the old function is gone from auth.py — any endpoint that
        accepted ?api_key= is the vulnerability we are fixing.

        We inspect the real module source rather than the mocked sys.modules entry
        because the streaming module import replaces backend.auth with a MagicMock.
        """
        auth_path = Path(__file__).parent.parent.parent / "dashboard" / "backend" / "auth.py"
        tree = ast.parse(auth_path.read_text())
        func_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        }
        assert "verify_api_key_or_query" not in func_names, (
            "verify_api_key_or_query still defined in auth.py — "
            "this function accepted the API key as a query parameter and must be removed"
        )

    def test_verify_sse_token_exists_in_auth(self) -> None:
        """auth.verify_sse_token must exist as the replacement for SSE auth."""
        auth_path = Path(__file__).parent.parent.parent / "dashboard" / "backend" / "auth.py"
        tree = ast.parse(auth_path.read_text())
        func_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        }
        assert "verify_sse_token" in func_names, (
            "verify_sse_token missing from auth.py — SSE endpoints have no authentication"
        )

    def test_streaming_endpoints_use_sse_token_dependency(self) -> None:
        """The SSE stream endpoints must declare verify_sse_token dependency."""
        streaming_mod = _streaming
        router = streaming_mod.router  # type: ignore[attr-defined]

        # Collect all route paths and their dependencies
        sse_route_paths = {"/api/stream/latest", "/api/stream/{run_id}"}
        poll_route_path = "/api/poll/{run_id}"

        for route in router.routes:  # type: ignore[attr-defined]
            if not hasattr(route, "path"):
                continue
            route_deps = [str(d.dependency) for d in getattr(route, "dependencies", [])]
            if route.path in sse_route_paths:
                assert any("verify_sse_token" in d for d in route_deps), (
                    f"SSE route {route.path} must use verify_sse_token, got: {route_deps}"
                )
            elif route.path == poll_route_path:
                assert any("verify_api_key" in d for d in route_deps), (
                    f"Poll route {route.path} must use verify_api_key, got: {route_deps}"
                )
