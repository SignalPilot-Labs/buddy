"""Regression tests for DockerLocalBackend image tag resolution.

The backend must use the same image as docker-compose.yml. Previously it
used a hardcoded "autofyn-sandbox" which diverged from the GHCR-tagged
images, causing per-run sandboxes to run stale code (missing entrypoint).
"""

import os
from unittest.mock import patch

import pytest

from utils.constants import ENV_KEY_IMAGE_TAG, SANDBOX_POOL_IMAGE_BASE
from sandbox_client.backends.docker_local_backend import DockerLocalBackend


class TestPoolImageTag:
    """Verify DockerLocalBackend resolves the correct image from AF_IMAGE_TAG."""

    def test_pool_image_uses_env_tag(self) -> None:
        """Backend image must be SANDBOX_POOL_IMAGE_BASE:AF_IMAGE_TAG."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "nightly"}):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:nightly"

    def test_pool_image_local_tag(self) -> None:
        """Local builds use :local tag."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "local"}):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:local"

    def test_pool_image_stable_tag(self) -> None:
        """Production installs use :stable tag."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "stable"}):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:stable"

    def test_pool_image_sha_tag(self) -> None:
        """Pinned installs use a commit SHA tag."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "abc1234"}):
            backend = DockerLocalBackend()
            assert backend._image == f"{SANDBOX_POOL_IMAGE_BASE}:abc1234"

    def test_pool_crashes_without_image_tag(self) -> None:
        """Backend must fail fast if AF_IMAGE_TAG is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_KEY_IMAGE_TAG, None)
            with pytest.raises(KeyError):
                DockerLocalBackend()
