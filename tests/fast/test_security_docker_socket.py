"""Regression tests for Docker socket world-writable chmod vulnerability.

Statically analyzes autofyn/entrypoint.sh to verify:
  1. No world-writable chmod on the docker socket.
  2. Group-based access mechanism is present.
  3. Socket existence guard is preserved.
"""

import re
from pathlib import Path


ENTRYPOINT_PATH = Path(__file__).parent.parent.parent / "autofyn" / "entrypoint.sh"


class TestDockerSocketEntrypoint:
    """Verify entrypoint.sh does not world-writable-chmod the Docker socket."""

    def test_entrypoint_no_chmod_666(self) -> None:
        """chmod 666 must not appear anywhere in the entrypoint script."""
        content = ENTRYPOINT_PATH.read_text()
        assert "chmod 666" not in content

    def test_entrypoint_no_world_writable_socket(self) -> None:
        """No chmod command must grant world-writable permissions to the docker socket."""
        content = ENTRYPOINT_PATH.read_text()
        world_writable_pattern = re.compile(
            r"chmod\s+(?:777|666|a\+rw|o\+rw|0777|0666)[^\n]*docker\.sock"
        )
        assert not world_writable_pattern.search(content), (
            "Found a world-writable chmod targeting docker.sock"
        )

    def test_entrypoint_uses_group_based_access(self) -> None:
        """Entrypoint must use group-based socket access: stat, group creation, and usermod."""
        content = ENTRYPOINT_PATH.read_text()
        assert "stat" in content, "Expected 'stat' to detect socket GID"
        assert re.search(r"groupadd|addgroup", content), (
            "Expected 'groupadd' or 'addgroup' to create group"
        )
        assert re.search(r"usermod\s+-aG|adduser", content), (
            "Expected 'usermod -aG' or 'adduser' to add agentuser to group"
        )

    def test_entrypoint_guards_socket_existence(self) -> None:
        """Socket operations must be guarded by a [ -S /var/run/docker.sock ] check."""
        content = ENTRYPOINT_PATH.read_text()
        assert "[ -S /var/run/docker.sock ]" in content, (
            "Expected socket existence guard '[ -S /var/run/docker.sock ]' to be present"
        )
