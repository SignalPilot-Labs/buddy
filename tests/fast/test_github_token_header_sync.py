"""Verify HEADER_GITHUB_TOKEN is in sync across autofyn and dashboard packages.

The token-in-header fix (PR #153) relies on both sides agreeing on the header
name. A typo on either end silently breaks the /branches and /diff/repo
proxies, so this test pins them together.
"""

from utils.constants import HEADER_GITHUB_TOKEN as AGENT_HEADER
from backend.constants import HEADER_GITHUB_TOKEN as DASHBOARD_HEADER


class TestGithubTokenHeaderSync:
    """Agent and dashboard must declare the same X-GitHub-Token header name."""

    def test_constants_match(self) -> None:
        assert AGENT_HEADER == DASHBOARD_HEADER

    def test_constant_value(self) -> None:
        assert AGENT_HEADER == "X-GitHub-Token"
