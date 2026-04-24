"""Regression tests for filesystem path confinement in the sandbox.

Covers: allowed paths, denied paths, traversal attacks, prefix boundary
safety, empty input, relative paths, and symlink traversal.

Finding: #6 — Path Traversal in File System Handlers (High severity).
"""

import os
from pathlib import Path

import pytest
from aiohttp import web

from handlers.path_validation import validate_fs_path


class TestFsPathConfinement:
    """validate_fs_path must confine all filesystem access to allowed dirs."""

    def test_allowed_paths(self) -> None:
        """Paths inside allowed prefixes must be returned without raising."""
        allowed = [
            "/home/agentuser/repo/src/main.py",
            "/home/agentuser/repo",
            "/tmp/round-1/architect.md",
            "/tmp",
            "/home/agentuser/.claude/settings.json",
            "/opt/autofyn/config/sandbox.yml",
        ]
        for path_str in allowed:
            result = validate_fs_path(path_str)
            assert str(result) == path_str, f"Expected {path_str}, got {result}"

    def test_denied_paths(self) -> None:
        """Paths outside all allowed prefixes must raise HTTPForbidden."""
        denied = [
            "/etc/passwd",
            "/proc/1/environ",
            "/home/agentuser/.ssh/id_rsa",
            "/var/run/docker.sock",
        ]
        for path_str in denied:
            with pytest.raises(web.HTTPForbidden):
                validate_fs_path(path_str)

    def test_traversal_attacks(self) -> None:
        """Paths using .. to escape allowed dirs must raise HTTPForbidden."""
        attacks = [
            "/home/agentuser/repo/../../etc/passwd",
            "/tmp/../etc/shadow",
            "/home/agentuser/repo/../.ssh/id_rsa",
        ]
        for path_str in attacks:
            with pytest.raises(web.HTTPForbidden):
                validate_fs_path(path_str)

    def test_prefix_boundary(self) -> None:
        """/tmpevil must NOT match the /tmp prefix."""
        with pytest.raises(web.HTTPForbidden):
            validate_fs_path("/tmpevil/data")

    def test_empty_path(self) -> None:
        """Empty string must raise HTTPBadRequest, not resolve to cwd."""
        with pytest.raises(web.HTTPBadRequest):
            validate_fs_path("")

    def test_relative_path_denied(self) -> None:
        """Relative paths that resolve outside allowed dirs must be denied.

        '../../etc/passwd' from any cwd under /home/agentuser/repo resolves
        to /etc/passwd, which is outside all allowed prefixes.
        """
        with pytest.raises(web.HTTPForbidden):
            validate_fs_path("../../etc/passwd")

    def test_symlink_traversal(self, tmp_path: Path) -> None:
        """Symlinks pointing outside allowed dirs must be denied.

        resolve() follows the symlink to its real target, exposing the true
        path for the allowlist check.
        """
        symlink_path = str(tmp_path) + "/evil_link"
        os.symlink("/etc/passwd", symlink_path)
        try:
            with pytest.raises(web.HTTPForbidden):
                validate_fs_path(symlink_path)
        finally:
            os.unlink(symlink_path)
