"""Regression tests for fetch_github_diff repo slug validation (Bug 5).

Ensures that malformed repo slugs raise ValueError immediately at the boundary
instead of silently producing wrong GitHub API queries.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from autofyn.utils.diff import fetch_github_diff


class TestFetchGithubDiffSlugValidation:
    """fetch_github_diff must reject invalid repo slugs before making HTTP calls."""

    @pytest.mark.asyncio
    async def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid repo slug"):
            await fetch_github_diff("", "main", "base", "token")

    @pytest.mark.asyncio
    async def test_no_slash_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid repo slug"):
            await fetch_github_diff("myrepo", "main", "base", "token")

    @pytest.mark.asyncio
    async def test_multiple_slashes_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid repo slug"):
            await fetch_github_diff("owner/repo/extra", "main", "base", "token")

    @pytest.mark.asyncio
    async def test_trailing_slash_owner_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid repo slug"):
            await fetch_github_diff("owner/", "main", "base", "token")

    @pytest.mark.asyncio
    async def test_leading_slash_repo_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid repo slug"):
            await fetch_github_diff("/repo", "main", "base", "token")

    @pytest.mark.asyncio
    async def test_bare_slash_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid repo slug"):
            await fetch_github_diff("/", "main", "base", "token")

    @pytest.mark.asyncio
    async def test_valid_slug_does_not_raise(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "diff output"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("autofyn.utils.diff.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_github_diff("owner/repo", "main", "base", "token")

        assert result == {"diff": "diff output"}
