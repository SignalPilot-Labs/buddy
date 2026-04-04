"""Local git repository detection utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

from cli.constants import GIT_REMOTE_ORIGIN, GIT_SLUG_SEPARATOR


def find_repo_root(cwd: Path) -> Path | None:
    """Walk parent dirs from cwd looking for .git. Return the root or None."""
    current = cwd.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def read_remote_slug(repo_root: Path) -> str | None:
    """Parse the 'origin' remote URL and return 'owner/repo' slug or None.

    Handles both HTTPS (https://github.com/owner/repo.git) and
    SSH (git@github.com:owner/repo.git) URL formats.
    """
    result = subprocess.run(
        ["git", "remote", "get-url", GIT_REMOTE_ORIGIN],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return _parse_slug(result.stdout.strip())


def detect_local_repo(cwd: Path) -> str | None:
    """Return the GitHub slug for the git repo at or above cwd, or None.

    Composes find_repo_root + read_remote_slug.
    """
    repo_root = find_repo_root(cwd)
    if repo_root is None:
        return None
    return read_remote_slug(repo_root)


def _parse_slug(url: str) -> str | None:
    """Extract 'owner/repo' from an HTTPS or SSH remote URL."""
    url = url.removesuffix(".git")
    if url.startswith("https://") or url.startswith("http://"):
        parts = url.split("/")
        if len(parts) >= 2:
            return GIT_SLUG_SEPARATOR.join(parts[-2:])
        return None
    # SSH format: git@github.com:owner/repo
    if ":" in url:
        after_colon = url.split(":", 1)[1]
        parts = after_colon.split(GIT_SLUG_SEPARATOR)
        if len(parts) >= 2:
            return GIT_SLUG_SEPARATOR.join(parts[-2:])
        return None
    return None
