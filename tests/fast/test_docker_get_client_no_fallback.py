"""Regression test for DockerLocalBackend.get_client fallback path removal.

Verifies that get_client() returns None when a run_key is in _containers
but has no corresponding entry in _clients, instead of silently creating
an unchecked client that may point to a dead container.
"""

import os
from unittest.mock import MagicMock, patch

from utils.constants import ENV_KEY_IMAGE_TAG, ENV_KEY_SANDBOX_SECRET
from sandbox_client.backends.docker_local_backend import DockerLocalBackend
from sandbox_client.client import SandboxClient


_SANDBOX_CONFIG_MOCK = {"vm_timeout_sec": 30}
_REQUIRED_ENV = {ENV_KEY_IMAGE_TAG: "test", ENV_KEY_SANDBOX_SECRET: "test"}


class TestDockerGetClientNoFallback:
    """get_client() must not fabricate a client when _clients has no entry."""

    def _make_backend(self) -> DockerLocalBackend:
        """Create a DockerLocalBackend with mocked Docker and config."""
        with (
            patch(
                "sandbox_client.backends.docker_local_backend.docker.from_env",
                return_value=MagicMock(),
            ),
            patch(
                "sandbox_client.backends.docker_local_backend.sandbox_config",
                return_value=_SANDBOX_CONFIG_MOCK,
            ),
            patch.dict(os.environ, _REQUIRED_ENV, clear=False),
        ):
            return DockerLocalBackend()

    def test_get_client_returns_none_when_container_exists_but_no_client(
        self,
    ) -> None:
        """If run_key is in _containers but not _clients, return None — not a fabricated client."""
        backend = self._make_backend()
        run_key = "abc123"

        # Simulate a container registered but no client cached
        backend._containers[run_key] = "container-id-xyz"

        result = backend.get_client(run_key)

        assert result is None
        # The fallback must NOT have inserted a client into _clients
        assert run_key not in backend._clients

    def test_get_client_returns_none_when_run_key_not_in_containers(
        self,
    ) -> None:
        """If run_key is not in _containers at all, return None."""
        backend = self._make_backend()

        result = backend.get_client("nonexistent-run")

        assert result is None

    def test_get_client_returns_cached_client_when_present(self) -> None:
        """If _clients has an entry for the run_key, return it."""
        backend = self._make_backend()
        run_key = "abc123"
        backend._containers[run_key] = "container-id-xyz"
        mock_client = MagicMock(spec=SandboxClient)
        backend._clients[run_key] = mock_client  # type: ignore[assignment]

        result = backend.get_client(run_key)

        assert result is mock_client
