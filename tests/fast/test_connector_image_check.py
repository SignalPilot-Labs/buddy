"""Regression tests for shell injection in _build_image_check for Slurm.

Verifies that paths with shell metacharacters and tilde prefixes
are properly quoted before being interpolated into a remote shell command.

Note: shlex.quote() only adds quoting when special characters are present.
Safe paths (no spaces, no metacharacters) are returned as-is.
"""

from __future__ import annotations

from cli.connector.server import _build_image_check, _quote_slurm_path


class TestBuildImageCheckSlurm:
    """Verify _build_image_check properly quotes Slurm image paths."""

    def test_metachar_injection_blocked(self) -> None:
        """Shell metacharacters in path must be treated literally, not executed."""
        start_cmd = "apptainer exec /tmp/$(whoami).sif"
        result = _build_image_check("slurm", start_cmd)
        assert result is not None
        check_cmd, image_path = result
        assert image_path == "/tmp/$(whoami).sif"
        # The shell command must quote the path so $() is not executed
        assert check_cmd == "test -f '/tmp/$(whoami).sif'"

    def test_tilde_path_uses_dollar_home(self) -> None:
        """Tilde paths must use $HOME so the shell expands home on the remote host."""
        start_cmd = "apptainer exec ~/sandboxes/autofyn.sif"
        result = _build_image_check("slurm", start_cmd)
        assert result is not None
        check_cmd, image_path = result
        assert image_path == "~/sandboxes/autofyn.sif"
        assert "$HOME" in check_cmd
        # rest of the tilde path (/sandboxes/autofyn.sif) must be quoted
        assert check_cmd == "test -f $HOME/sandboxes/autofyn.sif"

    def test_normal_absolute_path(self) -> None:
        """Ordinary absolute paths without special characters pass through shlex.quote unchanged."""
        start_cmd = "apptainer exec /opt/sandboxes/autofyn.sif"
        result = _build_image_check("slurm", start_cmd)
        assert result is not None
        check_cmd, image_path = result
        assert image_path == "/opt/sandboxes/autofyn.sif"
        assert check_cmd == "test -f /opt/sandboxes/autofyn.sif"

    def test_path_with_spaces_in_token_quoted(self) -> None:
        """A token containing spaces (passed as single token) must be shell-quoted."""
        # _quote_slurm_path is tested with an embedded space; _build_image_check
        # splits on whitespace so a path with spaces would appear as separate tokens.
        # We verify _quote_slurm_path handles this correctly for the helper itself.
        result = _quote_slurm_path("/home/user/my sandbox/test.sif")
        # shlex.quote wraps in single quotes when spaces are present
        assert result == "'/home/user/my sandbox/test.sif'"
        # The result starts and ends with single quotes (shell quoting)
        assert result.startswith("'") and result.endswith("'")

    def test_no_sif_returns_none(self) -> None:
        """Commands without a .sif token return None."""
        result = _build_image_check("slurm", "srun --partition=gpu python train.py")
        assert result is None

    def test_empty_start_cmd_returns_none(self) -> None:
        """Empty start command returns None without error."""
        result = _build_image_check("slurm", "")
        assert result is None

    def test_docker_sandbox_type_not_affected(self) -> None:
        """Docker sandbox type behavior is unchanged — still uses shlex.quote."""
        start_cmd = "docker run myrepo/myimage:latest"
        result = _build_image_check("docker", start_cmd)
        assert result is not None
        check_cmd, image_path = result
        assert image_path == "myrepo/myimage:latest"
        assert "docker image inspect" in check_cmd
        assert "myrepo/myimage:latest" in check_cmd

    def test_tilde_with_spaces_in_path(self) -> None:
        """Tilde path with spaces must quote only the rest after $HOME."""
        result = _quote_slurm_path("~/my sandbox/test.sif")
        assert result == "$HOME'/my sandbox/test.sif'"

    def test_semicolon_injection_blocked(self) -> None:
        """Semicolons in path must be shell-quoted to prevent command chaining."""
        result = _quote_slurm_path("/tmp/test;rm -rf /.sif")
        assert result == "'/tmp/test;rm -rf /.sif'"


class TestQuoteSlurmPath:
    """Unit tests for the _quote_slurm_path helper."""

    def test_absolute_path_safe_chars(self) -> None:
        """Absolute paths with only safe characters pass through unchanged."""
        assert _quote_slurm_path("/tmp/test.sif") == "/tmp/test.sif"

    def test_path_with_spaces_quoted(self) -> None:
        """Paths with spaces produce a single-quoted string safe for shell."""
        result = _quote_slurm_path("/home/user/my sandbox/test.sif")
        assert result == "'/home/user/my sandbox/test.sif'"

    def test_tilde_only_becomes_dollar_home(self) -> None:
        """Bare tilde path becomes $HOME with no trailing content."""
        assert _quote_slurm_path("~") == "$HOME"

    def test_tilde_slash_path_preserves_dollar_home(self) -> None:
        """Tilde prefix is replaced with $HOME; rest is passed through shlex.quote."""
        assert _quote_slurm_path("~/sandboxes/autofyn.sif") == "$HOME/sandboxes/autofyn.sif"

    def test_tilde_path_with_spaces(self) -> None:
        """Tilde path with spaces in the subdirectory is properly handled."""
        assert _quote_slurm_path("~/my sandbox/test.sif") == "$HOME'/my sandbox/test.sif'"

    def test_metacharacters_quoted(self) -> None:
        """Shell metacharacters like $() are escaped inside single quotes."""
        assert _quote_slurm_path("/tmp/$(whoami).sif") == "'/tmp/$(whoami).sif'"
