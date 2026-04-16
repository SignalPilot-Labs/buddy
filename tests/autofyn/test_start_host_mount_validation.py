"""F2+F3: _validate_start_host_mounts raises 422 on blocked mounts."""

import pytest
from fastapi import HTTPException

from endpoints import _validate_start_host_mounts


class TestStartHostMountValidation:
    """_validate_start_host_mounts raises HTTP 422 on invalid mounts."""

    def test_blocked_home_user_ssh(self) -> None:
        """F6 + F3: /home/victim/.ssh must be rejected."""
        mounts = [{"host_path": "/home/alice/.ssh", "container_path": "/mnt/ssh", "mode": "ro"}]
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_host_mounts(mounts)
        assert exc_info.value.status_code == 422

    def test_blocked_etc_mount(self) -> None:
        mounts = [{"host_path": "/etc/passwd", "container_path": "/mnt/etc", "mode": "ro"}]
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_host_mounts(mounts)
        assert exc_info.value.status_code == 422

    def test_blocked_proc_mount(self) -> None:
        mounts = [{"host_path": "/proc", "container_path": "/mnt/proc", "mode": "ro"}]
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_host_mounts(mounts)
        assert exc_info.value.status_code == 422

    def test_valid_mount_allowed(self) -> None:
        mounts = [{"host_path": "/srv/data", "container_path": "/mnt/data", "mode": "ro"}]
        _validate_start_host_mounts(mounts)  # Should not raise

    def test_none_mounts_allowed(self) -> None:
        _validate_start_host_mounts(None)  # Should not raise

    def test_empty_mounts_allowed(self) -> None:
        _validate_start_host_mounts([])  # Should not raise

    def test_blocked_home_subdir_exercises_f6(self) -> None:
        """F6: /home/* is now a blocked prefix, not just /home exact."""
        mounts = [{"host_path": "/home/bob/secrets", "container_path": "/mnt/sec", "mode": "ro"}]
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_host_mounts(mounts)
        assert exc_info.value.status_code == 422
