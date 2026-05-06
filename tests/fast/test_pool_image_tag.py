"""Regression tests for DockerLocalBackend image tag resolution.

The backend must use the same image as docker-compose.yml. Previously it
used a hardcoded "autofyn-sandbox" which diverged from the GHCR-tagged
images, causing per-run sandboxes to run stale code (missing entrypoint).
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from utils.constants import ENV_KEY_IMAGE_TAG, ENV_KEY_SANDBOX_SECRET, SANDBOX_POOL_IMAGE_BASE
from sandbox_client.backends.docker_local_backend import DockerLocalBackend


_SANDBOX_CONFIG_MOCK = {"vm_timeout_sec": 30}


class TestPoolImageTag:
    """Verify DockerLocalBackend resolves the correct image from AF_IMAGE_TAG."""

    def test_pool_image_uses_env_tag(self) -> None:
        """Backend image must be SANDBOX_POOL_IMAGE_BASE:AF_IMAGE_TAG."""
        with (
            patch("sandbox_client.backends.docker_local_backend.docker.from_env", return_value=MagicMock()),
            patch("sandbox_client.backends.docker_local_backend.sandbox_config", return_value=_SANDBOX_CONFIG_MOCK),
            patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "nightly", ENV_KEY_SANDBOX_SECRET: "test"}),
        ):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:nightly"

    def test_pool_image_local_tag(self) -> None:
        """Local builds use :local tag."""
        with (
            patch("sandbox_client.backends.docker_local_backend.docker.from_env", return_value=MagicMock()),
            patch("sandbox_client.backends.docker_local_backend.sandbox_config", return_value=_SANDBOX_CONFIG_MOCK),
            patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "local", ENV_KEY_SANDBOX_SECRET: "test"}),
        ):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:local"

    def test_pool_image_stable_tag(self) -> None:
        """Production installs use :stable tag."""
        with (
            patch("sandbox_client.backends.docker_local_backend.docker.from_env", return_value=MagicMock()),
            patch("sandbox_client.backends.docker_local_backend.sandbox_config", return_value=_SANDBOX_CONFIG_MOCK),
            patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "stable", ENV_KEY_SANDBOX_SECRET: "test"}),
        ):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:stable"

    def test_pool_image_sha_tag(self) -> None:
        """Pinned installs use a commit SHA tag."""
        with (
            patch("sandbox_client.backends.docker_local_backend.docker.from_env", return_value=MagicMock()),
            patch("sandbox_client.backends.docker_local_backend.sandbox_config", return_value=_SANDBOX_CONFIG_MOCK),
            patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "abc1234", ENV_KEY_SANDBOX_SECRET: "test"}),
        ):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:abc1234"

    def test_pool_crashes_without_image_tag(self) -> None:
        """Backend must fail fast if AF_IMAGE_TAG is not set."""
        with (
            patch("sandbox_client.backends.docker_local_backend.docker.from_env", return_value=MagicMock()),
            patch("sandbox_client.backends.docker_local_backend.sandbox_config", return_value=_SANDBOX_CONFIG_MOCK),
            patch.dict(os.environ, {ENV_KEY_SANDBOX_SECRET: "test"}, clear=False),
        ):
            os.environ.pop(ENV_KEY_IMAGE_TAG, None)
            with pytest.raises(KeyError):
                DockerLocalBackend()
