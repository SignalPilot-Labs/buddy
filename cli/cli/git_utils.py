"""Git utility helpers for the Buddy CLI."""

from __future__ import annotations

import subprocess


def is_git_repo(path: str) -> bool:
    """Return True if ``path`` is a git repository, False otherwise."""
    result = subprocess.run(
        ["git", "-C", path, "rev-parse", "--git-dir"],
        capture_output=True,
    )
    return result.returncode == 0
