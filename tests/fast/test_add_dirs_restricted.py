"""Regression test: add_dirs must only contain the skills directory.

The agent must NOT discover framework code (/opt/autofyn), dead paths
(/home/agentuser/research), or broad directories (/workspace). Only
the skills directory is needed for SDK skill discovery.
"""

from pathlib import Path

BOOTSTRAP_SRC = (
    Path(__file__).parent.parent.parent / "autofyn" / "lifecycle" / "bootstrap.py"
).read_text()


class TestAddDirsRestricted:
    """add_dirs must be locked down to skills only."""

    def test_add_dirs_contains_only_skills(self) -> None:
        """add_dirs must be exactly ['/opt/autofyn/.claude/skills']."""
        assert '"/opt/autofyn/.claude/skills"' in BOOTSTRAP_SRC

    def test_add_dirs_does_not_contain_framework_code(self) -> None:
        """Must not expose /opt/autofyn root — agent would search framework code."""
        # Extract the add_dirs line
        start = BOOTSTRAP_SRC.index('"add_dirs"')
        line = BOOTSTRAP_SRC[start:BOOTSTRAP_SRC.index("],", start) + 1]
        assert '"/opt/autofyn"' not in line or '"/opt/autofyn/.claude' in line

    def test_add_dirs_does_not_contain_dead_paths(self) -> None:
        """Must not include nonexistent directories."""
        start = BOOTSTRAP_SRC.index('"add_dirs"')
        line = BOOTSTRAP_SRC[start:BOOTSTRAP_SRC.index("],", start) + 1]
        assert "/home/agentuser/research" not in line
        assert "/workspace" not in line
