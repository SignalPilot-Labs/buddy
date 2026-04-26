"""Regression test: get_repo_list raises on corrupt JSON instead of returning [].

Previously corrupt JSON in the repos setting silently returned an empty list,
making users think their repos were deleted. Now raises CredentialDecryptionError.
"""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()

from backend.utils import CredentialDecryptionError, get_repo_list


class TestRepoListCorruptJson:
    """get_repo_list must raise on corrupt JSON, not silently return []."""

    @pytest.mark.asyncio
    async def test_corrupt_json_raises(self) -> None:
        """Invalid JSON in repos setting must raise CredentialDecryptionError."""
        mock_setting = MagicMock()
        mock_setting.value = "not valid json {{{"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)

        with pytest.raises(CredentialDecryptionError, match="invalid JSON"):
            await get_repo_list(mock_session)

    @pytest.mark.asyncio
    async def test_missing_setting_returns_empty(self) -> None:
        """No repos setting at all must return [] (not an error)."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        result = await get_repo_list(mock_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_valid_json_returns_list(self) -> None:
        """Valid JSON must return the parsed list."""
        import json

        repos = ["owner/repo1", "owner/repo2"]
        mock_setting = MagicMock()
        mock_setting.value = json.dumps(repos)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)

        result = await get_repo_list(mock_session)
        assert result == repos
