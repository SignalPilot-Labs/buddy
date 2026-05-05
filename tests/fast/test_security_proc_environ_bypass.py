"""Regression tests for SecurityGate interpreter-based bypass variants.

Covers two categories:
  1. /proc/environ reads via Python/Node/Perl interpreters — these were already
     blocked by the existing regex; tests confirm no regression.
  2. api.github.com access via Python/Node interpreters — previously unblocked
     because _check_github_api_direct required a curl/wget keyword; now fixed
     to block on api.github.com presence alone.
"""

from sdk.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"
PROC_DENY_MSG = "/proc/<pid>/environ is blocked"
GITHUB_DENY_MSG = "api.github.com"


def _make_gate() -> SecurityGate:
    """Build a SecurityGate with standard test config."""
    return SecurityGate(REPO, BRANCH)


class TestSecurityInterpreterBypasses:
    """Verify interpreter-based bypasses are blocked."""

    # ── /proc/environ via interpreters (already blocked, regression guard) ──

    def test_blocks_python_proc_environ(self) -> None:
        """python3 -c reading /proc/1/environ must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "python3 -c \"open('/proc/1/environ','rb').read()\""},
        )
        assert result is not None
        assert PROC_DENY_MSG in result

    def test_blocks_node_proc_environ(self) -> None:
        """node -e reading /proc/1/environ must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "node -e \"require('fs').readFileSync('/proc/1/environ')\""},
        )
        assert result is not None
        assert PROC_DENY_MSG in result

    def test_blocks_perl_proc_environ(self) -> None:
        """perl -e reading /proc/1/environ must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "perl -e \"open(F,'/proc/1/environ');print <F>\""},
        )
        assert result is not None
        assert PROC_DENY_MSG in result

    def test_blocks_python_proc_self_environ(self) -> None:
        """python3 -c reading /proc/self/environ must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "python3 -c \"open('/proc/self/environ','rb').read()\""},
        )
        assert result is not None
        assert PROC_DENY_MSG in result

    # ── api.github.com via interpreters (the fix being tested) ──

    def test_blocks_python_api_github(self) -> None:
        """python3 urllib accessing api.github.com must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {
                "command": (
                    "python3 -c \"import urllib.request; "
                    "urllib.request.urlopen('https://api.github.com/repos/foo/bar')\""
                )
            },
        )
        assert result is not None
        assert GITHUB_DENY_MSG in result.lower()

    def test_blocks_node_api_github(self) -> None:
        """node fetch targeting api.github.com must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "node -e \"fetch('https://api.github.com/repos/foo/bar')\""},
        )
        assert result is not None
        assert GITHUB_DENY_MSG in result.lower()

    def test_blocks_python_api_github_no_scheme(self) -> None:
        """python3 requests with no-scheme URL to api.github.com must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {
                "command": (
                    "python3 -c \"import requests; "
                    "requests.get('//api.github.com/repos/foo/bar')\""
                )
            },
        )
        assert result is not None
        assert GITHUB_DENY_MSG in result.lower()

    def test_blocks_python_api_github_socket(self) -> None:
        """python3 socket connecting to api.github.com must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {
                "command": (
                    "python3 -c \"import socket; "
                    "s=socket.create_connection(('api.github.com',443))\""
                )
            },
        )
        assert result is not None
        assert GITHUB_DENY_MSG in result.lower()

    # ── Allow tests ──

    def test_allows_python_other_url(self) -> None:
        """python3 accessing pypi.org must be allowed."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "python3 -c \"import requests; requests.get('https://pypi.org/')\""},
        )
        assert result is None

    def test_allows_grep_api_github(self) -> None:
        """grep for api.github.com in source code must be allowed."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "grep api.github.com README.md"},
        )
        assert result is None

    def test_allows_echo_api_github(self) -> None:
        """echo mentioning api.github.com must be allowed."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "echo 'Do not use api.github.com directly'"},
        )
        assert result is None

    def test_allows_python_non_secret_proc(self) -> None:
        """python3 reading /proc/cpuinfo must be allowed."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "python3 -c \"open('/proc/cpuinfo').read()\""},
        )
        assert result is None
