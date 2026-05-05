"""Verify remote mount path validation."""

from db.constants import validate_remote_mount_path


class TestRemoteMountValidation:
    """Remote mount path validation."""

    def test_valid_absolute_path(self) -> None:
        assert validate_remote_mount_path("/data/project") is None

    def test_valid_path_with_dots_and_dashes(self) -> None:
        assert validate_remote_mount_path("/home/user/.config/app-v2") is None

    def test_rejects_relative_path(self) -> None:
        result = validate_remote_mount_path("data/project")
        assert result is not None
        assert "absolute" in result

    def test_rejects_empty_path(self) -> None:
        result = validate_remote_mount_path("")
        assert result is not None

    def test_rejects_spaces(self) -> None:
        result = validate_remote_mount_path("/data/my project")
        assert result is not None
        assert "invalid characters" in result

    def test_rejects_shell_metacharacters(self) -> None:
        result = validate_remote_mount_path("/data/$(whoami)")
        assert result is not None

    def test_rejects_proc(self) -> None:
        result = validate_remote_mount_path("/proc/self")
        assert result is not None
        assert "blocked" in result

    def test_rejects_sys(self) -> None:
        result = validate_remote_mount_path("/sys/class")
        assert result is not None

    def test_rejects_dev(self) -> None:
        result = validate_remote_mount_path("/dev/null")
        assert result is not None

    def test_rejects_path_traversal_to_proc(self) -> None:
        """Path traversal via .. must be caught after normalization."""
        result = validate_remote_mount_path("/data/../proc/self")
        assert result is not None
        assert "blocked" in result

    def test_rejects_path_traversal_to_sys(self) -> None:
        """Path traversal via .. to /sys must be caught."""
        result = validate_remote_mount_path("/data/../sys/class")
        assert result is not None
        assert "blocked" in result
