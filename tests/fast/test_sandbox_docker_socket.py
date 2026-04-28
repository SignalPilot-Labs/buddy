"""Regression tests for sandbox Docker socket access.

Statically analyzes sandbox/entrypoint.sh to verify:
  1. No world-writable chmod on the docker socket.
  2. Group-based access mechanism is present.
  3. Socket existence guard is preserved.
  4. Drops to agentuser via gosu.
"""

import re
from pathlib import Path


ENTRYPOINT_PATH = Path(__file__).parent.parent.parent / "sandbox" / "entrypoint.sh"


class TestSandboxDockerSocketEntrypoint:
    """Verify sandbox entrypoint.sh grants Docker socket access safely."""

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

    def test_entrypoint_drops_to_agentuser(self) -> None:
        """Entrypoint must drop privileges to agentuser via gosu."""
        content = ENTRYPOINT_PATH.read_text()
        assert "gosu agentuser" in content, (
            "Expected 'gosu agentuser' to drop privileges before running the server"
        )

    def test_dockerfile_installs_gosu(self) -> None:
        """Dockerfile must install gosu for privilege dropping."""
        dockerfile = Path(__file__).parent.parent.parent / "sandbox" / "Dockerfile.gvisor"
        content = dockerfile.read_text()
        assert "gosu" in content, "Expected gosu to be installed in Dockerfile"

    def test_dockerfile_no_user_directive_before_entrypoint(self) -> None:
        """Dockerfile must NOT set USER before ENTRYPOINT — entrypoint needs root for group setup."""
        dockerfile = Path(__file__).parent.parent.parent / "sandbox" / "Dockerfile.gvisor"
        lines = dockerfile.read_text().splitlines()
        entrypoint_idx = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("ENTRYPOINT"):
                entrypoint_idx = i
                break
        assert entrypoint_idx is not None, "No ENTRYPOINT found in Dockerfile"
        for i in range(entrypoint_idx):
            stripped = lines[i].strip()
            assert not stripped.startswith("USER "), (
                f"USER directive at line {i + 1} before ENTRYPOINT — entrypoint needs root to modify groups"
            )
