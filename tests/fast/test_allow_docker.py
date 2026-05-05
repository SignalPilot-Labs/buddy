"""Tests for --allow-docker socket mount logic in DockerLocalBackend."""

import os
from unittest.mock import patch

from utils.constants import DOCKER_SOCKET_PATH, ENV_KEY_ALLOW_DOCKER, ENV_KEY_IMAGE_TAG
from sandbox_client.backends.docker_local_backend import DockerLocalBackend


# All tests need AF_IMAGE_TAG set — DockerLocalBackend.__init__ requires it.
_REQUIRED_ENV = {ENV_KEY_IMAGE_TAG: "test"}


class TestAllowDocker:
    """Verify _allow_docker flag controls socket mount behavior."""

    def test_allow_docker_false_by_default(self) -> None:
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            os.environ.pop(ENV_KEY_ALLOW_DOCKER, None)
            backend = DockerLocalBackend()
            assert backend._allow_docker is False

    def test_allow_docker_true_when_env_set(self) -> None:
        with patch.dict(os.environ, {**_REQUIRED_ENV, ENV_KEY_ALLOW_DOCKER: "1"}):
            backend = DockerLocalBackend()
            assert backend._allow_docker is True

    def test_allow_docker_true_for_true_string(self) -> None:
        with patch.dict(os.environ, {**_REQUIRED_ENV, ENV_KEY_ALLOW_DOCKER: "true"}):
            backend = DockerLocalBackend()
            assert backend._allow_docker is True

    def test_allow_docker_false_for_empty_string(self) -> None:
        with patch.dict(os.environ, {**_REQUIRED_ENV, ENV_KEY_ALLOW_DOCKER: ""}):
            backend = DockerLocalBackend()
            assert backend._allow_docker is False

    def test_allow_docker_false_for_zero(self) -> None:
        with patch.dict(os.environ, {**_REQUIRED_ENV, ENV_KEY_ALLOW_DOCKER: "0"}):
            backend = DockerLocalBackend()
            assert backend._allow_docker is False

    def test_socket_path_constant(self) -> None:
        assert DOCKER_SOCKET_PATH == "/var/run/docker.sock"
