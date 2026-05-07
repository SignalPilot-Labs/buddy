"""Tests for SandboxManager.resolve_start_cmd().

Verifies the unified start command resolution:
- Local Docker (sandbox_id=None) returns DEFAULT_DOCKER_START_CMD
- Remote sandbox reads default_start_cmd from settings config
- Missing remote config raises ValueError
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sandbox_client.backends.local_backend import DEFAULT_DOCKER_START_CMD
from sandbox_client.manager import SandboxManager


def _make_manager() -> SandboxManager:
    """Create a SandboxManager with mocked Docker client and sandbox config."""
    with (
        patch("sandbox_client.backends.local_backend.docker") as mock_docker,
        patch("sandbox_client.manager.sandbox_config") as mock_cfg,
    ):
        mock_docker.from_env.return_value = MagicMock()
        mock_cfg.return_value = {
            "image_tag": "test",
            "container_prefix": "autofyn-sandbox-",
            "volume_prefix": "autofyn-repo-",
            "network": "autofyn-net",
            "startup_timeout_sec": 30,
            "vm_timeout_sec": 30,
        }
        return SandboxManager()


class TestResolveStartCmd:
    """SandboxManager.resolve_start_cmd() unified resolution."""

    @pytest.mark.asyncio
    async def test_local_docker_returns_default(self) -> None:
        """sandbox_id=None must return DEFAULT_DOCKER_START_CMD."""
        mgr = _make_manager()
        result = await mgr.resolve_start_cmd(None)
        assert result == DEFAULT_DOCKER_START_CMD

    @pytest.mark.asyncio
    async def test_remote_reads_from_config(self) -> None:
        """Remote sandbox must read default_start_cmd from settings."""
        mgr = _make_manager()
        config = json.dumps({"default_start_cmd": "srun --partition=gpu my.sif"})
        with patch("sandbox_client.manager.get_setting_value", new_callable=AsyncMock, return_value=config):
            result = await mgr.resolve_start_cmd("sandbox-uuid")
        assert result == "srun --partition=gpu my.sif"

    @pytest.mark.asyncio
    async def test_missing_remote_config_raises(self) -> None:
        """Missing sandbox config must raise ValueError."""
        mgr = _make_manager()
        with patch("sandbox_client.manager.get_setting_value", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="No sandbox config found"):
                await mgr.resolve_start_cmd("nonexistent-id")

    @pytest.mark.asyncio
    async def test_local_and_remote_both_return_nonempty(self) -> None:
        """Both paths must return non-empty strings (fail-fast contract)."""
        mgr = _make_manager()

        local_cmd = await mgr.resolve_start_cmd(None)
        assert local_cmd.strip()

        config = json.dumps({"default_start_cmd": "docker run my-image"})
        with patch("sandbox_client.manager.get_setting_value", new_callable=AsyncMock, return_value=config):
            remote_cmd = await mgr.resolve_start_cmd("sandbox-uuid")
        assert remote_cmd.strip()
