"""Regression test: remote sandbox mounts must be loaded from the correct DB key.

Bug: read_credentials() always looked up ``host_mounts:{repo}`` (the local Docker
mount key). Remote sandbox mounts are stored under
``remote_mounts:{repo}:{sandbox_id}`` by the sandboxes endpoint.
When a remote sandbox was selected, host_mounts was always None — the agent
never received the configured mounts, so apptainer/docker started without -B/-v
flags and the sandbox could not access host directories.

Fix: read_credentials() now accepts a sandbox_id parameter. When present, it
looks up ``remote_mounts:{repo}:{sandbox_id}`` instead of ``host_mounts:{repo}``.
"""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()

import backend.utils as utils_mod  # noqa: E402

SANDBOX_UUID = "6256fbc5-8e8d-4a93-849d-73ac4ad5e7ef"
REPO = "org/repo"
REMOTE_KEY = f"remote_mounts:{REPO}:{SANDBOX_UUID}"
LOCAL_KEY = f"host_mounts:{REPO}"

SAMPLE_MOUNTS = [
    {"host_path": "/data/input", "container_path": "/home/agentuser/repo/data", "mode": "ro"},
    {"host_path": "/data/output", "container_path": "/home/agentuser/repo/output", "mode": "rw"},
]


def _make_setting(key: str, value: str) -> MagicMock:
    """Create a fake Setting row."""
    s = MagicMock()
    s.key = key
    s.value = value
    s.encrypted = False
    return s


def _make_session_ctx(get_map: dict[str, MagicMock | None]) -> Any:
    """Return an async context manager yielding a session with keyed get()."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=lambda model, key: get_map.get(key))
    session_mock.commit = AsyncMock()

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = get_map.get("claude_tokens")
    session_mock.execute = AsyncMock(return_value=execute_result)

    @asynccontextmanager
    async def ctx():
        yield session_mock

    return ctx


class TestRemoteMountsLoaded:
    """read_credentials must load remote mounts when sandbox_id is provided."""

    @pytest.mark.asyncio
    async def test_remote_sandbox_loads_remote_mounts_key(self) -> None:
        """With sandbox_id, read_credentials must use remote_mounts:{repo}:{sandbox_id}."""
        remote_setting = _make_setting(REMOTE_KEY, json.dumps(SAMPLE_MOUNTS))
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
            REMOTE_KEY: remote_setting,
            LOCAL_KEY: None,
        }

        with patch.object(utils_mod, "session", _make_session_ctx(get_map)):
            creds = await utils_mod.read_credentials(REPO, SANDBOX_UUID)

        assert creds["host_mounts"] == SAMPLE_MOUNTS

    @pytest.mark.asyncio
    async def test_local_sandbox_loads_host_mounts_key(self) -> None:
        """With sandbox_id=None, read_credentials must use host_mounts:{repo}."""
        local_setting = _make_setting(LOCAL_KEY, json.dumps(SAMPLE_MOUNTS))
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
            LOCAL_KEY: local_setting,
            REMOTE_KEY: None,
        }

        with patch.object(utils_mod, "session", _make_session_ctx(get_map)):
            creds = await utils_mod.read_credentials(REPO, None)

        assert creds["host_mounts"] == SAMPLE_MOUNTS

    @pytest.mark.asyncio
    async def test_remote_sandbox_ignores_local_mounts(self) -> None:
        """Remote sandbox must NOT fall back to local host_mounts."""
        local_setting = _make_setting(LOCAL_KEY, json.dumps(SAMPLE_MOUNTS))
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
            LOCAL_KEY: local_setting,
            REMOTE_KEY: None,
        }

        with patch.object(utils_mod, "session", _make_session_ctx(get_map)):
            creds = await utils_mod.read_credentials(REPO, SANDBOX_UUID)

        assert "host_mounts" not in creds

    @pytest.mark.asyncio
    async def test_no_repo_skips_mounts(self) -> None:
        """read_credentials(repo=None) must not attempt to read any mounts."""
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
        }

        with patch.object(utils_mod, "session", _make_session_ctx(get_map)):
            creds = await utils_mod.read_credentials(None, None)

        assert "host_mounts" not in creds
