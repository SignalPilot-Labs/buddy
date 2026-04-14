"""Tests for host mount validation and security blocking."""

from db.constants import validate_host_mount


class TestValidMounts:
    """Valid mount configurations must pass validation."""

    def test_readonly_data_mount(self) -> None:
        assert validate_host_mount("/data/models", "/mnt/host/models", "ro") is None

    def test_readwrite_mount(self) -> None:
        assert validate_host_mount("/home/user/output", "/mnt/host/output", "rw") is None

    def test_deeply_nested_path(self) -> None:
        assert validate_host_mount("/data/ml/datasets/v2", "/mnt/host/data", "ro") is None


class TestBlockedPaths:
    """Sensitive host paths must be rejected."""

    def test_root_blocked(self) -> None:
        error = validate_host_mount("/", "/mnt/host/root", "ro")
        assert error is not None
        assert "blocked" in error

    def test_etc_blocked(self) -> None:
        error = validate_host_mount("/etc", "/mnt/host/etc", "ro")
        assert error is not None

    def test_etc_subdir_blocked(self) -> None:
        error = validate_host_mount("/etc/ssh", "/mnt/host/ssh", "ro")
        assert error is not None

    def test_proc_blocked(self) -> None:
        error = validate_host_mount("/proc", "/mnt/host/proc", "ro")
        assert error is not None

    def test_sys_blocked(self) -> None:
        error = validate_host_mount("/sys", "/mnt/host/sys", "ro")
        assert error is not None

    def test_dev_blocked(self) -> None:
        error = validate_host_mount("/dev", "/mnt/host/dev", "ro")
        assert error is not None

    def test_var_run_blocked(self) -> None:
        error = validate_host_mount("/var/run/docker.sock", "/mnt/host/docker", "ro")
        assert error is not None

    def test_home_root_blocked(self) -> None:
        error = validate_host_mount("/home", "/mnt/host/home", "ro")
        assert error is not None
        assert "blocked" in error

    def test_home_subdir_allowed(self) -> None:
        assert validate_host_mount("/home/user/data", "/mnt/host/data", "ro") is None

    def test_boot_blocked(self) -> None:
        error = validate_host_mount("/boot", "/mnt/host/boot", "ro")
        assert error is not None

    def test_tmp_blocked(self) -> None:
        error = validate_host_mount("/tmp", "/mnt/host/tmp", "ro")
        assert error is not None


class TestBlockedContainerPaths:
    """Container paths that overwrite sandbox internals must be rejected."""

    def test_repo_root_blocked(self) -> None:
        """Cannot overwrite the repo volume root itself."""
        error = validate_host_mount("/data", "/home/agentuser/repo", "ro")
        assert error is not None
        assert "sandbox internals" in error

    def test_repo_subdir_allowed(self) -> None:
        """Mounting into repo subdirs is the primary use case (e.g. data/)."""
        assert validate_host_mount("/data", "/home/agentuser/repo/data", "ro") is None

    def test_claude_dir_blocked(self) -> None:
        error = validate_host_mount("/data", "/home/agentuser/.claude", "ro")
        assert error is not None
        assert "sandbox internals" in error

    def test_claude_subdir_blocked(self) -> None:
        error = validate_host_mount("/data", "/home/agentuser/.claude/sessions", "ro")
        assert error is not None

    def test_other_container_path_allowed(self) -> None:
        assert validate_host_mount("/data", "/mnt/data", "ro") is None

    def test_home_agentuser_other_allowed(self) -> None:
        assert validate_host_mount("/data", "/home/agentuser/data", "ro") is None


class TestInvalidInputs:
    """Malformed inputs must be rejected."""

    def test_relative_host_path(self) -> None:
        error = validate_host_mount("data/models", "/mnt/host/models", "ro")
        assert error is not None
        assert "absolute" in error

    def test_empty_host_path(self) -> None:
        error = validate_host_mount("", "/mnt/host/x", "ro")
        assert error is not None

    def test_relative_container_path(self) -> None:
        error = validate_host_mount("/data", "mnt/host/data", "ro")
        assert error is not None
        assert "absolute" in error

    def test_empty_container_path(self) -> None:
        error = validate_host_mount("/data", "", "ro")
        assert error is not None

    def test_invalid_mode(self) -> None:
        error = validate_host_mount("/data", "/mnt/host/data", "rwx")
        assert error is not None
        assert "mode" in error

    def test_path_traversal_blocked(self) -> None:
        error = validate_host_mount("/data/../etc/shadow", "/mnt/host/x", "ro")
        assert error is not None
        assert ".." in error

    def test_trailing_slash_normalized(self) -> None:
        """Trailing slash on a blocked path must still be caught."""
        error = validate_host_mount("/etc/", "/mnt/host/etc", "ro")
        assert error is not None
