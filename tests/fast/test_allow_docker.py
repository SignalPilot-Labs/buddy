"""Tests for --allow-docker socket mount logic in DockerLocalBackend."""

import os
from unittest.mock import MagicMock, patch

from utils.constants import DOCKER_SOCKET_PATH, ENV_KEY_ALLOW_DOCKER, ENV_KEY_IMAGE_TAG
from sandbox_client.backends.local_backend import DockerLocalBackend


def _make_backend(allow_docker: str | None = None) -> DockerLocalBackend:
    """Instantiate DockerLocalBackend with mocked Docker client and sandbox_config.

    Sets AF_IMAGE_TAG to 'test' and optionally controls AF_ALLOW_DOCKER.
    Pass allow_docker=None to leave the env var unset.
    """
    env: dict[str, str] = {ENV_KEY_IMAGE_TAG: "test"}
    if allow_docker is not None:
        env[ENV_KEY_ALLOW_DOCKER] = allow_docker

    with (
        patch("sandbox_client.backends.local_backend.docker.from_env", return_value=MagicMock()),
        patch(
            "sandbox_client.backends.local_backend.sandbox_config",
            return_value={"vm_timeout_sec": 30, "health_timeout_sec": 5},
        ),
        patch.dict(os.environ, env, clear=False),
    ):
        if allow_docker is None:
            os.environ.pop(ENV_KEY_ALLOW_DOCKER, None)
        return DockerLocalBackend()


class TestAllowDocker:
    """Verify _allow_docker flag controls socket mount behavior."""

    def test_allow_docker_false_by_default(self) -> None:
        backend = _make_backend(allow_docker=None)
        assert backend._allow_docker is False

    def test_allow_docker_true_when_env_set(self) -> None:
        backend = _make_backend(allow_docker="1")
        assert backend._allow_docker is True

    def test_allow_docker_true_for_true_string(self) -> None:
        backend = _make_backend(allow_docker="true")
        assert backend._allow_docker is True

    def test_allow_docker_false_for_empty_string(self) -> None:
        backend = _make_backend(allow_docker="")
        assert backend._allow_docker is False

    def test_allow_docker_false_for_zero(self) -> None:
        backend = _make_backend(allow_docker="0")
        assert backend._allow_docker is False

    def test_socket_path_constant(self) -> None:
        assert DOCKER_SOCKET_PATH == "/var/run/docker.sock"
