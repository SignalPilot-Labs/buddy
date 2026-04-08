"""Tests for --allow-docker socket mount logic in SandboxPool."""

import os
from unittest.mock import patch

from utils.constants import DOCKER_SOCKET_PATH, ENV_KEY_ALLOW_DOCKER
from sandbox_manager.pool import SandboxPool


class TestAllowDocker:
    """Verify _allow_docker flag controls socket mount behavior."""

    def test_allow_docker_false_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_KEY_ALLOW_DOCKER, None)
            pool = SandboxPool()
            assert pool._allow_docker is False

    def test_allow_docker_true_when_env_set(self) -> None:
        with patch.dict(os.environ, {ENV_KEY_ALLOW_DOCKER: "1"}):
            pool = SandboxPool()
            assert pool._allow_docker is True

    def test_allow_docker_true_for_true_string(self) -> None:
        with patch.dict(os.environ, {ENV_KEY_ALLOW_DOCKER: "true"}):
            pool = SandboxPool()
            assert pool._allow_docker is True

    def test_allow_docker_false_for_empty_string(self) -> None:
        with patch.dict(os.environ, {ENV_KEY_ALLOW_DOCKER: ""}):
            pool = SandboxPool()
            assert pool._allow_docker is False

    def test_allow_docker_false_for_zero(self) -> None:
        with patch.dict(os.environ, {ENV_KEY_ALLOW_DOCKER: "0"}):
            pool = SandboxPool()
            assert pool._allow_docker is False

    def test_socket_path_constant(self) -> None:
        assert DOCKER_SOCKET_PATH == "/var/run/docker.sock"
