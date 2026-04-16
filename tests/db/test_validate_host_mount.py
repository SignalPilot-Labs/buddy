"""Tests for validate_host_mount (F6 focus: /home as blocked prefix)."""

from db.constants import validate_host_mount


class TestHostMountF6:
    """/home is now a blocked prefix, not an exact blocked path."""

    def test_home_alice_ssh_blocked(self) -> None:
        error = validate_host_mount("/home/alice/.ssh", "/mnt/ssh", "ro")
        assert error is not None

    def test_home_bob_repo_blocked(self) -> None:
        error = validate_host_mount("/home/bob/repo", "/mnt/repo", "ro")
        assert error is not None

    def test_home_exact_blocked(self) -> None:
        error = validate_host_mount("/home", "/mnt/home", "ro")
        assert error is not None
        assert "blocked" in error

    def test_srv_data_allowed(self) -> None:
        assert validate_host_mount("/srv/data", "/mnt/srv", "ro") is None

    def test_opt_autofyn_data_allowed(self) -> None:
        assert validate_host_mount("/opt/autofyn-data", "/mnt/autofyn", "ro") is None

    def test_homely_data_not_blocked(self) -> None:
        """Path that starts with /home string but is not under /home/ prefix."""
        assert validate_host_mount("/homely/data", "/mnt/homely", "ro") is None

    def test_data_with_home_in_path_not_blocked(self) -> None:
        """'/var/home' should not be blocked by the '/home' prefix rule."""
        assert validate_host_mount("/var/home/user", "/mnt/data", "ro") is None
