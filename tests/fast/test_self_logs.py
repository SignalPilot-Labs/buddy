"""Tests for get_self_logs — agent reads its own container logs."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from docker.errors import NotFound
from sandbox_client.pool import SandboxPool


class TestGetSelfLogs:
    """SandboxPool.get_self_logs reads the agent container."""

    @pytest.mark.asyncio
    async def test_returns_agent_container_lines(self) -> None:

        pool = SandboxPool.__new__(SandboxPool)
        mock_container = MagicMock()
        mock_container.logs.return_value = b"2026-04-15T19:52:19Z line1\n2026-04-15T19:52:20Z line2\n"

        mock_docker = MagicMock()
        mock_docker.containers.get.return_value = mock_container
        pool._docker = mock_docker

        lines = await pool.get_self_logs(10)

        mock_docker.containers.get.assert_called_once_with("autofyn-agent")
        assert len(lines) == 2
        assert "line1" in lines[0]
        assert "line2" in lines[1]

    @pytest.mark.asyncio
    async def test_returns_empty_on_not_found(self) -> None:
        pool = SandboxPool.__new__(SandboxPool)
        mock_docker = MagicMock()
        mock_docker.containers.get.side_effect = NotFound("gone")
        pool._docker = mock_docker

        lines = await pool.get_self_logs(10)
        assert lines == []
