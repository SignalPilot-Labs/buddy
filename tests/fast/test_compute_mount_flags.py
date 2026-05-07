"""Unit tests for DockerLocalBackend._compute_mount_flags().

Verifies that host mounts are converted to correct -v flags, invalid
mounts are skipped, Docker socket is included when allow_docker is set,
and paths are shell-quoted.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")
os.environ.setdefault("AF_IMAGE_TAG", "test")

with patch("docker.from_env", return_value=MagicMock()):
    from sandbox_client.backends.local_backend import DockerLocalBackend

from utils.constants import DOCKER_SOCKET_PATH


def _make_backend(allow_docker: bool) -> DockerLocalBackend:
    """Build a DockerLocalBackend with controlled allow_docker flag."""
    env = {
        "AF_IMAGE_TAG": "test",
        "AF_ALLOW_DOCKER": "1" if allow_docker else "",
    }
    with (
        patch("docker.from_env", return_value=MagicMock()),
        patch.dict(os.environ, env),
    ):
        return DockerLocalBackend()


class TestComputeMountFlags:
    """_compute_mount_flags must produce correct -v flags."""

    def test_no_mounts_no_docker_returns_empty(self) -> None:
        """No mounts and allow_docker=False returns empty string."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags(None)
        assert result == ""

    def test_no_mounts_empty_list_returns_empty(self) -> None:
        """Empty mount list returns empty string (no Docker socket)."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags([])
        assert result == ""

    def test_docker_socket_included_when_allowed(self) -> None:
        """allow_docker=True includes Docker socket mount."""
        backend = _make_backend(allow_docker=True)
        result = backend._compute_mount_flags(None)
        assert f"-v {DOCKER_SOCKET_PATH}:{DOCKER_SOCKET_PATH}:rw" in result

    def test_docker_socket_excluded_when_not_allowed(self) -> None:
        """allow_docker=False excludes Docker socket mount."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags([
            {"host_path": "/data", "container_path": "/data", "mode": "ro"},
        ])
        assert DOCKER_SOCKET_PATH not in result

    def test_single_mount_produces_correct_flag(self) -> None:
        """Single valid mount produces one -v flag."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags([
            {"host_path": "/host/data", "container_path": "/container/data", "mode": "ro"},
        ])
        assert "-v" in result
        assert "/host/data" in result
        assert "/container/data" in result
        assert ":ro" in result

    def test_multiple_mounts_produce_multiple_flags(self) -> None:
        """Multiple mounts produce space-separated -v flags."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags([
            {"host_path": "/a", "container_path": "/x", "mode": "ro"},
            {"host_path": "/b", "container_path": "/y", "mode": "rw"},
        ])
        parts = result.split("-v ")
        # First part is empty string before first -v
        assert len(parts) == 3, f"Expected 2 -v flags, got: {result}"

    def test_invalid_mount_is_skipped(self) -> None:
        """Mount with invalid path is skipped, valid mount is kept."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags([
            {"host_path": "../escape", "container_path": "/data", "mode": "ro"},
            {"host_path": "/valid", "container_path": "/data", "mode": "ro"},
        ])
        assert "../escape" not in result
        assert "/valid" in result

    def test_default_mode_is_ro(self) -> None:
        """Mount without explicit mode defaults to ro."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags([
            {"host_path": "/data", "container_path": "/data"},
        ])
        assert ":ro" in result

    def test_paths_with_spaces_are_quoted(self) -> None:
        """Paths containing spaces are shell-quoted."""
        backend = _make_backend(allow_docker=False)
        result = backend._compute_mount_flags([
            {"host_path": "/my data", "container_path": "/container data", "mode": "ro"},
        ])
        # shlex.quote wraps in single quotes
        assert "'/my data'" in result
        assert "'/container data'" in result

    def test_docker_socket_combined_with_mounts(self) -> None:
        """Docker socket and user mounts are both included."""
        backend = _make_backend(allow_docker=True)
        result = backend._compute_mount_flags([
            {"host_path": "/data", "container_path": "/data", "mode": "rw"},
        ])
        assert DOCKER_SOCKET_PATH in result
        assert "/data" in result
