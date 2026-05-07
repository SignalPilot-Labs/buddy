"""Regression tests for DockerLocalBackend image tag resolution.

The backend must use the same image as docker-compose.yml. Previously it
used a hardcoded "autofyn-sandbox" which diverged from the GHCR-tagged
images, causing per-run sandboxes to run stale code (missing entrypoint).
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from utils.constants import ENV_KEY_IMAGE_TAG, SANDBOX_POOL_IMAGE_BASE
from sandbox_client.backends.local_backend import DockerLocalBackend, DEFAULT_DOCKER_START_CMD


def _make_backend(tag: str) -> DockerLocalBackend:
    """Build a DockerLocalBackend with mocked Docker and the given image tag."""
    with (
        patch("sandbox_client.backends.local_backend.docker.from_env", return_value=MagicMock()),
        patch("sandbox_client.backends.local_backend.sandbox_config", return_value={"vm_timeout_sec": 30, "health_timeout_sec": 5}),
        patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: tag}),
    ):
        return DockerLocalBackend()


class TestPoolImageTag:
    """Verify DockerLocalBackend resolves the correct image from AF_IMAGE_TAG."""

    def test_pool_image_uses_env_tag(self) -> None:
        """Backend image tag must come from AF_IMAGE_TAG env var."""
        backend = _make_backend("nightly")
        assert backend._image_tag == "nightly"

    def test_pool_image_local_tag(self) -> None:
        """Local builds use :local tag."""
        backend = _make_backend("local")
        assert backend._image_tag == "local"

    def test_pool_image_stable_tag(self) -> None:
        """Production installs use :stable tag."""
        backend = _make_backend("stable")
        assert backend._image_tag == "stable"

    def test_pool_image_sha_tag(self) -> None:
        """Pinned installs use a commit SHA tag."""
        backend = _make_backend("abc1234")
        assert backend._image_tag == "abc1234"

    def test_pool_crashes_without_image_tag(self) -> None:
        """Backend must fail fast if AF_IMAGE_TAG is not set."""
        with (
            patch("sandbox_client.backends.local_backend.docker.from_env", return_value=MagicMock()),
            patch("sandbox_client.backends.local_backend.sandbox_config", return_value={"vm_timeout_sec": 30, "health_timeout_sec": 5}),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop(ENV_KEY_IMAGE_TAG, None)
            with pytest.raises(KeyError):
                DockerLocalBackend()

    def test_default_start_cmd_contains_image_base(self) -> None:
        """Default start command must reference the correct image base."""
        assert SANDBOX_POOL_IMAGE_BASE in DEFAULT_DOCKER_START_CMD
        assert "$AF_IMAGE_TAG" in DEFAULT_DOCKER_START_CMD
