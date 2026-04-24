"""Regression test: _host_mounts_block uses container_path key, not target.

Previously line 97 of prompts/loader.py accessed m['target'] but mount dicts
from pool.py use 'container_path'. Any run with host mounts configured would
crash with KeyError: 'target'.
"""

import pytest

from prompts.loader import _host_mounts_block


class TestHostMountsKey:
    """_host_mounts_block must use container_path, matching the real mount dict shape."""

    def test_container_path_key_renders_correctly(self) -> None:
        """Real mount dict shape from pool.py uses container_path."""
        out = _host_mounts_block([{"host_path": "/host/data", "container_path": "/data", "mode": "ro"}])
        assert "`/data` (read-only)" in out
        assert out.startswith("Host mounts:")

    def test_missing_container_path_raises_key_error(self) -> None:
        """Fail fast: a mount dict missing container_path raises KeyError, no silent fallback."""
        with pytest.raises(KeyError):
            _host_mounts_block([{"host_path": "/host/data", "mode": "ro"}])

    def test_multiple_mounts_with_real_structure(self) -> None:
        """Multiple mounts matching pool.py structure render in order."""
        mounts = [
            {"host_path": "/host/a", "container_path": "/a", "mode": "rw"},
            {"host_path": "/host/b", "container_path": "/b", "mode": "ro"},
        ]
        out = _host_mounts_block(mounts)
        lines = out.splitlines()
        assert lines[0] == "Host mounts:"
        assert lines[1] == "- `/a` (read-write)"
        assert lines[2] == "- `/b` (read-only)"

    def test_target_key_raises_key_error(self) -> None:
        """Using the old wrong key 'target' must raise KeyError, not silently work."""
        with pytest.raises(KeyError):
            _host_mounts_block([{"target": "/data", "mode": "ro"}])
