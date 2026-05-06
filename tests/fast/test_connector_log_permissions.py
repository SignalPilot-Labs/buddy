"""Regression test for connector log file permissions vulnerability.

Verifies that ~/.autofyn/.connector.log is created with mode 0600 (owner read/write only),
not world-readable 0644 from default umask.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli.constants import SECURE_FILE_MODE


class TestConnectorLogPermissions:
    """Verify connector log file is not world-readable."""

    def test_log_file_not_world_readable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Log file must be created with 0600, not default 0644."""
        monkeypatch.setattr("cli.commands.services.AUTOFYN_HOME", str(tmp_path))

        with patch("cli.commands.services._wait_port_free", return_value=True), \
             patch("cli.commands.services._wait_port_ready", return_value=True), \
             patch("cli.commands.services._kill_port_pids"), \
             patch("subprocess.Popen") as mock_popen:

            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            from cli.commands.services import _start_connector
            _start_connector()

        log_file = tmp_path / ".connector.log"
        assert log_file.exists(), "Log file should be created"

        mode = os.stat(log_file).st_mode
        assert not (mode & stat.S_IRGRP), "Log file should not be group-readable"
        assert not (mode & stat.S_IWGRP), "Log file should not be group-writable"
        assert not (mode & stat.S_IROTH), "Log file should not be world-readable"
        assert not (mode & stat.S_IWOTH), "Log file should not be world-writable"

        assert mode & stat.S_IRUSR, "Log file should be owner-readable"
        assert mode & stat.S_IWUSR, "Log file should be owner-writable"

    def test_existing_file_permissions_corrected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If log file exists with wrong permissions, they should be corrected."""
        monkeypatch.setattr("cli.commands.services.AUTOFYN_HOME", str(tmp_path))

        log_file = tmp_path / ".connector.log"
        log_file.write_text("old logs\n")
        os.chmod(log_file, 0o644)

        mode_before = os.stat(log_file).st_mode & 0o777
        assert mode_before == 0o644, "Test setup: file should start world-readable"

        with patch("cli.commands.services._wait_port_free", return_value=True), \
             patch("cli.commands.services._wait_port_ready", return_value=True), \
             patch("cli.commands.services._kill_port_pids"), \
             patch("subprocess.Popen") as mock_popen:

            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            from cli.commands.services import _start_connector
            _start_connector()

        mode_after = os.stat(log_file).st_mode & 0o777
        assert mode_after == SECURE_FILE_MODE, f"Permissions should be corrected to 0o600, got {oct(mode_after)}"

    def test_secure_file_mode_constant_is_0600(self) -> None:
        """SECURE_FILE_MODE constant must be 0600 (owner read/write only)."""
        assert SECURE_FILE_MODE == 0o600
