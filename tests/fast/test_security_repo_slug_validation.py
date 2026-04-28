"""Regression tests for path traversal via repo slug in settings endpoints.

Verifies:
  1. validate_repo_slug accepts a valid owner/repo slug.
  2. validate_repo_slug rejects path traversal payloads (400).
  3. validate_repo_slug rejects other invalid formats (400).
  4. All 6 {repo:path} endpoints call the validator (integration).
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Stub out modules that require live services before importing settings endpoint.
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()
if "db.models" not in sys.modules:
    sys.modules["db.models"] = MagicMock()

_auth_mock = MagicMock()
_auth_mock.verify_api_key = MagicMock(return_value=None)
sys.modules["backend.auth"] = _auth_mock

import backend.endpoints.settings as settings_mod  # noqa: E402
from backend.models import SaveMcpServersRequest, SaveMountsRequest, SaveRepoEnvRequest  # noqa: E402


def _null_session_ctx() -> Any:
    """Return an async context manager yielding a session whose .get() returns None."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=None)
    session_mock.delete = AsyncMock()
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def ctx():  # type: ignore[return]
        yield session_mock

    return ctx


class TestRepoSlugValidation:
    """Regression tests for repo slug path traversal vulnerability (Finding 7)."""

    # ── Direct helper tests ──────────────────────────────────────────────────

    def test_valid_slug_passes(self) -> None:
        """A standard owner/repo slug must be returned unchanged."""
        result = settings_mod.validate_repo_slug("owner/repo")
        assert result == "owner/repo"

    def test_valid_slug_with_dashes_and_dots(self) -> None:
        """Slugs with dashes, underscores, and dots must be accepted."""
        result = settings_mod.validate_repo_slug("my-org/my-repo.v2")
        assert result == "my-org/my-repo.v2"

    def test_path_traversal_with_dotdot_raises_400(self) -> None:
        """Path traversal using '../..' segments must be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("owner/repo/../../../etc")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid repo slug format"

    def test_multi_segment_traversal_raises_400(self) -> None:
        """A multi-segment path traversal slug must be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("owner/repo/../../etc/passwd")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid repo slug format"

    def test_slug_with_spaces_raises_400(self) -> None:
        """Slugs containing spaces must be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("owner name/repo")
        assert exc_info.value.status_code == 400

    def test_empty_slug_raises_400(self) -> None:
        """Empty string must be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("")
        assert exc_info.value.status_code == 400

    def test_slug_without_slash_raises_400(self) -> None:
        """A slug with only an owner (no slash) must be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("owneronly")
        assert exc_info.value.status_code == 400

    def test_slug_with_unicode_raises_400(self) -> None:
        """Unicode characters are not permitted in repo slugs (ASCII-only pattern)."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("owñer/repö")
        assert exc_info.value.status_code == 400

    def test_slug_with_null_byte_raises_400(self) -> None:
        """Null bytes must be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("owner/repo\x00evil")
        assert exc_info.value.status_code == 400

    def test_dotdot_owner_and_repo_raises_400(self) -> None:
        """../.. must be rejected even though dots are valid chars."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("../..")
        assert exc_info.value.status_code == 400

    def test_dotdot_repo_component_raises_400(self) -> None:
        """owner/.. must be rejected — '..' is not a valid repo name."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("owner/..")
        assert exc_info.value.status_code == 400

    def test_dotdot_owner_component_raises_400(self) -> None:
        """../repo must be rejected — '..' is not a valid owner name."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("../repo")
        assert exc_info.value.status_code == 400

    def test_single_dot_components_raises_400(self) -> None:
        """./. must be rejected — '.' is not a valid owner or repo name."""
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug("./.")
        assert exc_info.value.status_code == 400

    def test_overlong_slug_raises_400(self) -> None:
        """Slugs exceeding GITHUB_REPO_MAX_LEN must be rejected with HTTP 400."""
        long_owner = "a" * 200
        long_repo = "b" * 200
        with pytest.raises(HTTPException) as exc_info:
            settings_mod.validate_repo_slug(f"{long_owner}/{long_repo}")
        assert exc_info.value.status_code == 400

    # ── Endpoint integration tests ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_repo_env_rejects_traversal(self) -> None:
        """GET /repos/{repo}/env must reject a path traversal repo slug."""
        with pytest.raises(HTTPException) as exc_info:
            await settings_mod.get_repo_env("owner/repo/../../../secret")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_repo_env_accepts_valid(self) -> None:
        """GET /repos/{repo}/env must succeed with a valid slug."""
        with patch.object(settings_mod, "session", _null_session_ctx()):
            result = await settings_mod.get_repo_env("owner/repo")
        assert result["repo"] == "owner/repo"

    @pytest.mark.asyncio
    async def test_save_repo_env_rejects_traversal(self) -> None:
        """PUT /repos/{repo}/env must reject a path traversal repo slug."""
        with pytest.raises(HTTPException) as exc_info:
            await settings_mod.save_repo_env(
                "owner/repo/../../../etc", SaveRepoEnvRequest(env_vars={})
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_repo_mounts_rejects_traversal(self) -> None:
        """GET /repos/{repo}/mounts must reject a path traversal repo slug."""
        with pytest.raises(HTTPException) as exc_info:
            await settings_mod.get_repo_mounts("owner/../../etc/passwd")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_save_repo_mounts_rejects_traversal(self) -> None:
        """PUT /repos/{repo}/mounts must reject a path traversal repo slug."""
        with pytest.raises(HTTPException) as exc_info:
            body = SaveMountsRequest(mounts=[])
            await settings_mod.save_repo_mounts("owner/../../etc", body)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_repo_mcp_servers_rejects_traversal(self) -> None:
        """GET /repos/{repo}/mcp-servers must reject a path traversal repo slug."""
        with pytest.raises(HTTPException) as exc_info:
            await settings_mod.get_repo_mcp_servers("bad/../../../path")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_save_repo_mcp_servers_rejects_traversal(self) -> None:
        """PUT /repos/{repo}/mcp-servers must reject a path traversal repo slug."""
        with pytest.raises(HTTPException) as exc_info:
            body = SaveMcpServersRequest(servers={})
            await settings_mod.save_repo_mcp_servers("bad/../../path", body)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_remove_repo_rejects_traversal(self) -> None:
        """DELETE /repos/{repo} must reject a path traversal repo slug."""
        with pytest.raises(HTTPException) as exc_info:
            await settings_mod.remove_repo("owner/../../etc/passwd")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_remove_repo_rejects_unicode(self) -> None:
        """DELETE /repos/{repo} must reject unicode characters (stricter than old re.match)."""
        with pytest.raises(HTTPException) as exc_info:
            await settings_mod.remove_repo("owñer/repö")
        assert exc_info.value.status_code == 400
