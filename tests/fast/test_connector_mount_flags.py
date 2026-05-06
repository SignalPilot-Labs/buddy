"""Unit tests for connector mount flag computation functions.

Verifies that _compute_apptainer_binds() produces -B flags for Slurm
and _compute_docker_volumes() produces -v flags for remote Docker.
Both must shell-quote paths and handle empty lists.
"""

from __future__ import annotations

from cli.connector.startup import _compute_apptainer_binds, _compute_docker_volumes


class TestComputeApptainerBinds:
    """_compute_apptainer_binds must produce correct -B flags for Apptainer."""

    def test_empty_list_returns_empty(self) -> None:
        """No mounts returns empty string."""
        assert _compute_apptainer_binds([]) == ""

    def test_single_mount_produces_bind_flag(self) -> None:
        """Single mount produces one -B flag."""
        result = _compute_apptainer_binds([
            {"host_path": "/data", "container_path": "/mnt/data", "mode": "ro"},
        ])
        assert result == "-B /data:/mnt/data:ro"

    def test_multiple_mounts_space_separated(self) -> None:
        """Multiple mounts produce space-separated -B flags."""
        result = _compute_apptainer_binds([
            {"host_path": "/a", "container_path": "/x", "mode": "ro"},
            {"host_path": "/b", "container_path": "/y", "mode": "rw"},
        ])
        assert "-B /a:/x:ro" in result
        assert "-B /b:/y:rw" in result

    def test_paths_with_spaces_are_quoted(self) -> None:
        """Paths with spaces are shell-quoted."""
        result = _compute_apptainer_binds([
            {"host_path": "/my data", "container_path": "/mnt/my data", "mode": "ro"},
        ])
        assert "'/my data'" in result
        assert "'/mnt/my data'" in result

    def test_rw_mode_preserved(self) -> None:
        """Read-write mode is correctly included in the flag."""
        result = _compute_apptainer_binds([
            {"host_path": "/data", "container_path": "/data", "mode": "rw"},
        ])
        assert result.endswith(":rw")


class TestComputeDockerVolumes:
    """_compute_docker_volumes must produce correct -v flags for Docker."""

    def test_empty_list_returns_empty(self) -> None:
        """No mounts returns empty string."""
        assert _compute_docker_volumes([]) == ""

    def test_single_mount_produces_volume_flag(self) -> None:
        """Single mount produces one -v flag."""
        result = _compute_docker_volumes([
            {"host_path": "/data", "container_path": "/mnt/data", "mode": "ro"},
        ])
        assert result == "-v /data:/mnt/data:ro"

    def test_multiple_mounts_space_separated(self) -> None:
        """Multiple mounts produce space-separated -v flags."""
        result = _compute_docker_volumes([
            {"host_path": "/a", "container_path": "/x", "mode": "ro"},
            {"host_path": "/b", "container_path": "/y", "mode": "rw"},
        ])
        assert "-v /a:/x:ro" in result
        assert "-v /b:/y:rw" in result

    def test_paths_with_spaces_are_quoted(self) -> None:
        """Paths with spaces are shell-quoted."""
        result = _compute_docker_volumes([
            {"host_path": "/my data", "container_path": "/mnt/my data", "mode": "ro"},
        ])
        assert "'/my data'" in result
        assert "'/mnt/my data'" in result
