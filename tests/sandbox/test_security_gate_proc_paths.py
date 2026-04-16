"""F1: /proc/* path blocking applies to ALL tools, not just Bash.

Tests that _check_proc_paths fires as a universal first-pass in check_permission
for Read, Write, Edit, Glob, Grep, and Bash tools.
"""

import pytest

from session.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"


def _make_gate() -> SecurityGate:
    return SecurityGate(REPO, BRANCH)


class TestProcPathsBlockedAcrossTools:
    """Sensitive /proc paths must be denied for every tool that accepts a path."""

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/proc/1/environ"}),
        ("Write", {"file_path": "/proc/1/environ"}),
        ("Edit", {"file_path": "/proc/1/environ"}),
        ("Grep", {"path": "/proc/1/environ", "pattern": "TOKEN"}),
        ("Grep", {"path": "/tmp", "pattern": "/proc/1/environ"}),
        ("Glob", {"pattern": "/proc/1/environ"}),
        ("Bash", {"command": "cat /proc/1/environ"}),
    ])
    def test_proc_1_environ_denied(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} with {input_data} should be denied"
        assert "proc" in result.lower() or "credential" in result.lower()

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/proc/self/environ"}),
        ("Write", {"file_path": "/proc/self/environ"}),
        ("Edit", {"file_path": "/proc/self/environ"}),
        ("Grep", {"path": "/proc/self/environ", "pattern": "KEY"}),
        ("Glob", {"pattern": "/proc/self/environ"}),
        ("Bash", {"command": "cat /proc/self/environ"}),
    ])
    def test_proc_self_environ_denied(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} with {input_data} should be denied"

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/proc/123/environ"}),
        ("Write", {"file_path": "/proc/123/environ"}),
        ("Edit", {"file_path": "/proc/123/environ"}),
        ("Glob", {"pattern": "/proc/123/environ"}),
    ])
    def test_proc_pid_environ_denied(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} with {input_data} should be denied"

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/proc/1/cmdline"}),
        ("Write", {"file_path": "/proc/1/cmdline"}),
        ("Glob", {"pattern": "/proc/*/cmdline"}),
        ("Bash", {"command": "cat /proc/1/cmdline"}),
    ])
    def test_proc_cmdline_denied(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} with {input_data} should be denied"

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/proc/kcore"}),
        ("Write", {"file_path": "/proc/kcore"}),
        ("Bash", {"command": "dd if=/proc/kcore of=/tmp/mem"}),
    ])
    def test_proc_kcore_denied(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} with {input_data} should be denied"

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/proc/1/mem"}),
        ("Read", {"file_path": "/proc/1/maps"}),
        ("Bash", {"command": "cat /proc/1/mem"}),
        ("Bash", {"command": "cat /proc/1/maps"}),
    ])
    def test_proc_mem_maps_denied(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} with {input_data} should be denied"

    @pytest.mark.parametrize("tool,input_data", [
        ("Bash", {"command": "head /proc/*/environ"}),
        ("Glob", {"pattern": "/proc/*/environ"}),
    ])
    def test_proc_glob_environ_denied(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} with {input_data} should be denied"


class TestProcPathsPositiveCases:
    """Non-sensitive /proc paths must still be allowed."""

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/proc/1/status"}),
        ("Read", {"file_path": "/proc/self/status"}),
        ("Read", {"file_path": "/proc/cpuinfo"}),
        ("Bash", {"command": "cat /proc/cpuinfo"}),
        ("Bash", {"command": "cat /proc/self/status"}),
        ("Bash", {"command": "cat /proc/1/status"}),
    ])
    def test_allowed_proc_paths(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is None, f"{tool} with {input_data} should be allowed"

    @pytest.mark.parametrize("tool,input_data", [
        ("Read", {"file_path": "/procstats/data.txt"}),
        ("Glob", {"pattern": "/procstats/reports"}),
    ])
    def test_non_proc_paths_allowed(self, tool: str, input_data: dict) -> None:
        """Paths that start with /proc-like strings but aren't /proc paths must be allowed."""
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is None, f"{tool} with {input_data} should be allowed"
