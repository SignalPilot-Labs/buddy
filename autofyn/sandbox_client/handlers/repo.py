"""Repo handler — typed wrapper around sandbox `/repo/*`.

All actual git and gh subprocess work happens on the sandbox side, which
tracks the active working branch and refuses to mutate anything else.
This class is a thin HTTP wrapper — no business logic, no retries, no
branch-name validation (the server does that).
"""

import logging

import httpx

log = logging.getLogger("sandbox_client.repo")


class Repo:
    """Handler for sandbox `/repo/*` HTTP endpoints.

    Public API — setup:
        clone(repo, token, base_branch, timeout)
        ensure_base_branch(base, timeout)
    Public API — branches:
        create_branch(name, base, timeout)
        checkout_branch(name, timeout)
        current_branch(timeout)
    Public API — commits / push:
        has_changes(timeout)
        commit(message, timeout)
        push(timeout)
        commits_ahead(base, timeout)
    Public API — diff:
        branch_diff(base, timeout)
    Public API — PR:
        find_pr(timeout)
        create_or_update_pr(title, description, base, timeout)
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    # ── Setup ──────────────────────────────────────────────────────────

    async def clone(
        self, repo: str, token: str, base_branch: str, timeout: int,
    ) -> None:
        """Clone `repo` into the sandbox and persist auth in the local config."""
        await self._post("/repo/clone", {
            "repo": repo,
            "token": token,
            "base_branch": base_branch,
            "timeout": timeout,
        })

    async def ensure_base_branch(self, base: str, timeout: int) -> None:
        """Verify the base branch exists on the configured remote."""
        await self._post("/repo/ensure_base_branch", {
            "base": base, "timeout": timeout,
        })

    # ── Branches ───────────────────────────────────────────────────────

    async def create_branch(
        self, name: str, base: str, timeout: int,
    ) -> None:
        """Reset to origin/base and create a new working branch."""
        await self._post("/repo/create_branch", {
            "name": name, "base": base, "timeout": timeout,
        })

    async def checkout_branch(self, name: str, timeout: int) -> None:
        """Fetch and checkout an existing branch (for resume)."""
        await self._post("/repo/checkout_branch", {
            "name": name, "timeout": timeout,
        })

    async def current_branch(self, timeout: int) -> str:
        """Return the current git HEAD branch name."""
        data = await self._post("/repo/current_branch", {"timeout": timeout})
        return str(data.get("branch", ""))

    # ── Commits / push ─────────────────────────────────────────────────

    async def has_changes(self, timeout: int) -> bool:
        """True if the working tree has uncommitted or staged changes."""
        data = await self._post("/repo/has_changes", {"timeout": timeout})
        return bool(data.get("has_changes"))

    async def commit(self, message: str, timeout: int) -> bool:
        """Stage everything and commit. Returns True if a commit was made."""
        data = await self._post("/repo/commit", {
            "message": message, "timeout": timeout,
        })
        return bool(data.get("committed"))

    async def push(self, timeout: int) -> None:
        """Push the active branch to origin."""
        await self._post("/repo/push", {"timeout": timeout})

    async def commits_ahead(self, base: str, timeout: int) -> int:
        """Commit count between origin/base and HEAD."""
        data = await self._post("/repo/commits_ahead", {
            "base": base, "timeout": timeout,
        })
        return int(data.get("count", 0))

    # ── Diff ───────────────────────────────────────────────────────────

    async def branch_diff(self, base: str, timeout: int) -> list[dict]:
        """File-level diff stats between the active branch and base."""
        data = await self._post("/repo/branch_diff", {
            "base": base, "timeout": timeout,
        })
        return list(data.get("files", []))

    # ── PR ─────────────────────────────────────────────────────────────

    async def find_pr(self, timeout: int) -> str | None:
        """Look up an existing PR for the active branch. None if absent."""
        data = await self._post("/repo/find_pr", {"timeout": timeout})
        url = data.get("url")
        return url if isinstance(url, str) else None

    async def create_or_update_pr(
        self, title: str, description: str, base: str, timeout: int,
    ) -> str:
        """Create a PR, or edit an existing one. Returns the PR URL."""
        data = await self._post("/repo/pr", {
            "title": title,
            "description": description,
            "base": base,
            "timeout": timeout,
        })
        url = data.get("url")
        if not isinstance(url, str) or not url:
            raise RuntimeError("sandbox /repo/pr returned no url")
        return url

    # ── Private ────────────────────────────────────────────────────────

    async def _post(self, path: str, body: dict) -> dict:
        """Send a POST and return the JSON response dict."""
        resp = await self._http.post(path, json=body)
        resp.raise_for_status()
        return resp.json()
