"""F6: /home moved from BLOCKED_MOUNT_PATHS to BLOCKED_MOUNT_PREFIXES.

Tests that /home/* subdirectories are now blocked (not just /home exactly).
"""

from db.constants import validate_host_mount


class TestHomeBlockedAsPrefix:
    """After F6, /home is a blocked prefix — all subdirs are rejected."""

    def test_home_alice_ssh_blocked(self) -> None:
        error = validate_host_mount("/home/alice/.ssh", "/mnt/ssh", "ro")
        assert error is not None

    def test_home_bob_repo_blocked(self) -> None:
        error = validate_host_mount("/home/bob/repo", "/mnt/repo", "ro")
        assert error is not None

    def test_home_itself_blocked(self) -> None:
        error = validate_host_mount("/home", "/mnt/home", "ro")
        assert error is not None
        assert "blocked" in error

    def test_srv_data_still_allowed(self) -> None:
        assert validate_host_mount("/srv/data", "/mnt/srv", "ro") is None

    def test_opt_autofyn_still_allowed(self) -> None:
        assert validate_host_mount("/opt/autofyn-data", "/mnt/autofyn", "ro") is None

    def test_homely_data_not_blocked(self) -> None:
        """Path that starts with /home string but is not under /home/ prefix."""
        assert validate_host_mount("/homely/data", "/mnt/homely", "ro") is None
