"""Repo handler — typed wrapper around sandbox `/repo/*`.

Three endpoints, three fixed phases of an agent run:

    bootstrap  clone + verify base + create working branch (one call)
    save       commit + push per-round changes (one call per round)
    teardown   commit leftovers + push + PR + diff (one call at run end)

Each endpoint is a single HTTP round-trip that bundles every git/gh
operation the phase needs. The sandbox owns sequencing, validation, and
branch/push integrity — this class is a thin typed client.
"""

import logging

import httpx

from utils.models import SaveResult, TeardownResult
from utils.secrets import scrub_secrets

log = logging.getLogger("sandbox_client.repo")

_SECRET_BODY_KEYS: frozenset[str] = frozenset({"token", "claude_token", "git_token"})


class Repo:
    """Typed HTTP wrapper around sandbox `/repo/*` endpoints.

    Public API:
        bootstrap(repo, token, base_branch, working_branch, timeout)
        save(message, timeout) -> SaveResult
        teardown(pr_title, pr_description, base, timeout) -> TeardownResult
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def bootstrap(
        self,
        repo: str,
        token: str,
        base_branch: str,
        working_branch: str,
        timeout: int,
    ) -> None:
        """Clone the repo, verify the base branch, create the working branch."""
        await self._post("/repo/bootstrap", {
            "repo": repo,
            "token": token,
            "base_branch": base_branch,
            "working_branch": working_branch,
            "timeout": timeout,
        })

    async def save(self, message: str, timeout: int) -> SaveResult:
        """Per-round commit + push. No-op if the working tree is clean."""
        data = await self._post("/repo/save", {
            "message": message,
            "timeout": timeout,
        })
        return SaveResult(
            committed=bool(data["committed"]),
            pushed=bool(data["pushed"]),
            push_error=data["push_error"],
        )

    async def teardown(
        self,
        pr_title: str,
        pr_description: str,
        base: str,
        timeout: int,
    ) -> TeardownResult:
        """End-of-run commit + push + PR + diff. One HTTP round-trip."""
        data = await self._post("/repo/teardown", {
            "pr_title": pr_title,
            "pr_description": pr_description,
            "base": base,
            "timeout": timeout,
        })
        return TeardownResult(
            auto_committed=bool(data["auto_committed"]),
            commits_ahead=int(data["commits_ahead"]),
            pushed=bool(data["pushed"]),
            push_error=data["push_error"],
            pr_url=data["pr_url"],
            pr_error=data["pr_error"],
            diff_stats=list(data["diff_stats"]),
        )

    async def diff(self) -> dict:
        """Get the full unified diff from the sandbox."""
        return await self._post("/repo/diff", {})

    async def diff_stats(self) -> list[dict]:
        """Get per-file diff stats (path, added, removed, status).

        Cheap counterpart to `diff()` — returns only numstat + name-status
        output, a few hundred bytes, intended for the dashboard's periodic
        polling of the Changes-panel header.
        """
        data = await self._post("/repo/diff/stats", {})
        return list(data["files"])

    # ── Private ────────────────────────────────────────────────────────

    async def _post(self, path: str, body: dict) -> dict:
        """Send a POST and return the JSON response dict."""
        resp = await self._http.post(path, json=body)
        if resp.status_code >= 400:
            scrubbed = scrub_secrets(resp.text, [body.get(k) for k in _SECRET_BODY_KEYS])
            raise RuntimeError(
                f"sandbox {path} -> {resp.status_code}: {scrubbed[:1000]}"
            )
        return resp.json()
