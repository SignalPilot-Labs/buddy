"""Regression tests for SandboxPool image tag resolution.

The pool must use the same image as docker-compose.yml. Previously it
used a hardcoded "autofyn-sandbox" which diverged from the GHCR-tagged
images, causing per-run sandboxes to run stale code (missing entrypoint).
"""

import os
from unittest.mock import patch

import pytest

from utils.constants import ENV_KEY_IMAGE_TAG, SANDBOX_POOL_IMAGE_BASE
from sandbox_client.pool import SandboxPool


class TestPoolImageTag:
    """Verify SandboxPool resolves the correct image from AF_IMAGE_TAG."""

    def test_pool_image_uses_env_tag(self) -> None:
        """Pool image must be SANDBOX_POOL_IMAGE_BASE:AF_IMAGE_TAG."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "nightly"}):
            pool = SandboxPool()
            assert pool._image == f"{SANDBOX_POOL_IMAGE_BASE}:nightly"

    def test_pool_image_local_tag(self) -> None:
        """Local builds use :local tag."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "local"}):
            pool = SandboxPool()
            assert pool._image == f"{SANDBOX_POOL_IMAGE_BASE}:local"

    def test_pool_image_stable_tag(self) -> None:
        """Production installs use :stable tag."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "stable"}):
            pool = SandboxPool()
            assert pool._image == f"{SANDBOX_POOL_IMAGE_BASE}:stable"

    def test_pool_image_sha_tag(self) -> None:
        """Pinned installs use a commit SHA tag."""
        with patch.dict(os.environ, {ENV_KEY_IMAGE_TAG: "abc1234"}):
            pool = SandboxPool()
            assert pool._image == f"{SANDBOX_POOL_IMAGE_BASE}:abc1234"

    def test_pool_crashes_without_image_tag(self) -> None:
        """Pool must fail fast if AF_IMAGE_TAG is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_KEY_IMAGE_TAG, None)
            with pytest.raises(KeyError):
                SandboxPool()
