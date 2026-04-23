"""Route handlers for diff endpoints: repo diff, diff stats, tmp diff, and branch listing."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import httpx

from fastapi import FastAPI, Header, HTTPException

from utils.constants import (
    GITHUB_API_BASE_URL,
    GITHUB_API_TIMEOUT_SEC,
    GITHUB_BRANCHES_PER_PAGE,
    GITHUB_DIFF_CACHE_MAX,
    GITHUB_ERROR_PREVIEW_LEN,
    HEADER_GITHUB_TOKEN,
    ROUND_ARCHIVE_AGENT_DIR,
    ROUND_DIR_NAME_RE,
)
from utils.diff import fetch_github_diff

if TYPE_CHECKING:
    from sandbox_client.client import SandboxClient
    from server import AgentServer

log = logging.getLogger("endpoints.diff")

# LRU cache for completed-run diffs (GitHub API path). Live sandbox
# diffs are not cached — they change every round and caching them
# serves stale data forever. Bounded by GITHUB_DIFF_CACHE_MAX so the
# cache can't grow unbounded over the agent's lifetime.
_github_diff_cache: OrderedDict[str, str] = OrderedDict()

_ROUND_DIR_NAME = re.compile(ROUND_DIR_NAME_RE)


def _build_tmp_diff(entries: list[tuple[str, str]]) -> str:
    """Render a list of (rel_path, content) tuples as a unified 'new file' diff."""
    parts: list[str] = []
    for rel, content in entries:
        lines = content.splitlines()
        header = (
            f"diff --git a/{rel} b/{rel}\n"
            f"new file mode 100644\n"
            f"--- /dev/null\n"
            f"+++ b/{rel}\n"
            f"@@ -0,0 +1,{len(lines)} @@"
        )
        body = "\n".join(f"+{line}" for line in lines)
        parts.append(f"{header}\n{body}")
    return "\n".join(parts)


async def _collect_tmp_from_sandbox(
    client: "SandboxClient",
) -> list[tuple[str, str]]:
    """Read /tmp/round-* from the live sandbox. Rounds are fetched in parallel."""
    entries_raw = await client.file_system.ls("/tmp")
    round_names = sorted(n for n in entries_raw if _ROUND_DIR_NAME.match(n))
    if not round_names:
        return []
    results = await asyncio.gather(*(
        client.file_system.read_dir(f"/tmp/{n}") for n in round_names
    ))
    entries: list[tuple[str, str]] = []
    for round_name, files in zip(round_names, results):
        if not files:
            continue
        for fname, content in sorted(files.items()):
            entries.append((f"tmp/{round_name}/{fname}", content))
    return entries


def _collect_tmp_from_archive(run_id: str) -> list[tuple[str, str]]:
    """Read archived round files from the agent's host volume."""
    archive_root = Path(ROUND_ARCHIVE_AGENT_DIR) / run_id
    if not archive_root.is_dir():
        return []
    entries: list[tuple[str, str]] = []
    for round_dir in sorted(archive_root.iterdir()):
        if not round_dir.is_dir():
            continue
        for f in sorted(round_dir.iterdir()):
            if not f.is_file():
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            entries.append((f"tmp/{round_dir.name}/{f.name}", content))
    return entries


def register_diff_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register diff route handlers."""

    @app.get("/diff/repo")
    async def diff_repo(
        run_id: str,
        branch: str,
        base: str,
        repo: str,
        token: Annotated[str, Header(alias=HEADER_GITHUB_TOKEN)],
        source: Literal["sandbox", "github"] = "sandbox",
    ):
        """Full unified diff.

        `source` controls the retrieval path:
        - "sandbox" (default): diff against the live working tree via the
          sandbox client. Returns 409 if no sandbox is available — the
          caller (dashboard) should only use this mode for active runs.
        - "github": compare via GitHub API. For completed runs whose
          sandbox is gone. The agent caches these in an LRU so repeated
          views don't re-fetch.

        The dashboard decides which source based on run.status; the agent
        never silently falls through from sandbox to GitHub, which
        previously caused a placeholder branch ("pending") to collide
        with a real remote branch and return an unrelated diff.
        """
        if source == "github":
            if run_id in _github_diff_cache:
                _github_diff_cache.move_to_end(run_id)
                return {"diff": _github_diff_cache[run_id]}
            result = await fetch_github_diff(repo, branch, base, token)
            if "error" in result:
                raise HTTPException(status_code=result.get("status", 502), detail=result["error"])
            _github_diff_cache[run_id] = result["diff"]
            if len(_github_diff_cache) > GITHUB_DIFF_CACHE_MAX:
                _github_diff_cache.popitem(last=False)
            return result

        # Sandbox path — active runs only.
        client = server.pool().get_client(run_id)
        if not client:
            raise HTTPException(status_code=409, detail="No active sandbox for run")
        try:
            return await client.repo.diff()
        except Exception as exc:
            log.warning("Sandbox diff failed for %s: %s", run_id, exc)
            raise HTTPException(status_code=502, detail=f"Sandbox unreachable: {exc}")

    @app.get("/diff/repo/stats")
    async def diff_repo_stats(run_id: str):
        """Per-file diff stats without transferring the full diff body.

        Intended for the dashboard Changes-panel header poll. Only handles
        live runs — completed-run stats live in the dashboard DB (written
        at teardown) and the dashboard short-circuits before calling this.
        """
        client = server.pool().get_client(run_id)
        if not client:
            raise HTTPException(status_code=409, detail="No active sandbox for run")
        try:
            files = await client.repo.diff_stats()
        except Exception as exc:
            log.warning("Sandbox diff_stats failed for %s: %s", run_id, exc)
            raise HTTPException(status_code=502, detail=f"Sandbox unreachable: {exc}")
        return {"files": files}

    @app.get("/diff/tmp")
    async def diff_tmp(run_id: str):
        """Unified diff of round files (all treated as new files).

        During round 1 the archive on the host volume is still empty — the files
        only exist inside the live sandbox at /tmp/round-N. So we check the
        sandbox first and fall back to the archive for completed runs.
        """
        client = server.pool().get_client(run_id)
        entries = (
            await _collect_tmp_from_sandbox(client)
            if client
            else _collect_tmp_from_archive(run_id)
        )
        return {"diff": _build_tmp_diff(entries)}

    @app.get("/branches")
    async def list_branches(
        repo: str,
        token: Annotated[str, Header(alias=HEADER_GITHUB_TOKEN)],
    ):
        """List branches on the GitHub remote for the given repo.

        Called by the dashboard's StartRunModal to populate the "branch from"
        dropdown. The dashboard passes the git token it has in settings; we
        just proxy to the GitHub API. No sandbox needed because this runs
        before any run has started.
        """
        if "/" not in repo:
            raise HTTPException(status_code=400, detail="repo must be owner/name")
        url = f"{GITHUB_API_BASE_URL}/repos/{repo}/branches"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(timeout=GITHUB_API_TIMEOUT_SEC) as client:
            resp = await client.get(url, headers=headers, params={"per_page": GITHUB_BRANCHES_PER_PAGE})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"GitHub API error: {resp.text[:GITHUB_ERROR_PREVIEW_LEN]}",
            )
        data = resp.json()
        return [b["name"] for b in data]
