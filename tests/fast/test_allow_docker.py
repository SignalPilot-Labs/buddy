"""Tests for --allow-docker socket mount logic in DockerLocalBackend."""

import asyncio
import os
from unittest.mock import MagicMock, patch

from utils.constants import DOCKER_SOCKET_PATH, ENV_KEY_ALLOW_DOCKER, ENV_KEY_IMAGE_TAG
from sandbox_client.backends.local_backend import DockerLocalBackend


# All tests need AF_IMAGE_TAG set — DockerLocalBackend.__init__ requires it.
_REQUIRED_ENV = {ENV_KEY_IMAGE_TAG: "test"}

_DOCKER_MOCK_PATCHES = (
    "sandbox_client.backends.local_backend.docker.from_env",
    "sandbox_client.backends.local_backend.sandbox_config",
)


def _make_backend(extra_env: dict | None = None) -> DockerLocalBackend:
    """Build a DockerLocalBackend with mocked Docker and sandbox config."""
    env = {**_REQUIRED_ENV, **(extra_env or {})}
    with (
        patch(_DOCKER_MOCK_PATCHES[0], return_value=MagicMock()),
        patch(_DOCKER_MOCK_PATCHES[1], return_value={"vm_timeout_sec": 30, "health_timeout_sec": 5}),
        patch.dict(os.environ, env),
    ):
        return DockerLocalBackend(asyncio.Event())


class TestAllowDocker:
    """Verify _allow_docker flag controls socket mount behavior."""

    def test_allow_docker_false_by_default(self) -> None:
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            os.environ.pop(ENV_KEY_ALLOW_DOCKER, None)
            backend = _make_backend()
            assert backend._allow_docker is False

    def test_allow_docker_true_when_env_set(self) -> None:
        backend = _make_backend({ENV_KEY_ALLOW_DOCKER: "1"})
        assert backend._allow_docker is True

    def test_allow_docker_true_for_true_string(self) -> None:
        backend = _make_backend({ENV_KEY_ALLOW_DOCKER: "true"})
        assert backend._allow_docker is True

    def test_allow_docker_false_for_empty_string(self) -> None:
        backend = _make_backend({ENV_KEY_ALLOW_DOCKER: ""})
        assert backend._allow_docker is False

    def test_allow_docker_false_for_zero(self) -> None:
        backend = _make_backend({ENV_KEY_ALLOW_DOCKER: "0"})
        assert backend._allow_docker is False

    def test_socket_path_constant(self) -> None:
        assert DOCKER_SOCKET_PATH == "/var/run/docker.sock"
