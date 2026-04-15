"""HTTP route handlers for the agent server.

Thin routing. `/start` wires up an ActiveRun + background task; the
control endpoints push events into the run's UserInbox; health
reads the TimeLock for per-run time info.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

import httpx
from fastapi import FastAPI, HTTPException

from utils import db
from utils.diff import extract_file_patch
from utils.constants import (
    ENV_KEY_CLAUDE_TOKEN,
    ENV_KEY_GIT_TOKEN,
    MAX_CONCURRENT_RUNS,
    RUN_ID_LOG_PREFIX_LEN,
)
from utils.models import (
    ActiveRun,
    HealthResponse,
    HealthRunEntry,
    InjectRequest,
    ResumeRequest,
    StartRequest,
    StopRequest,
)

if TYPE_CHECKING:
    from server import AgentServer

log = logging.getLogger("endpoints")


def _to_patch_response(full_diff: str, path: str) -> dict:
    """Extract a single file's patch from a full diff, or raise 404."""
    patch = extract_file_patch(full_diff, path)
    if patch is None:
        raise HTTPException(status_code=404, detail=f"File {path} not found in diff")
    return {"patch": patch, "path": path}


def _merge_tokens_into_env(
    env: dict[str, str] | None,
    claude_token: str | None,
    git_token: str | None,
) -> dict[str, str] | None:
    """Merge per-run tokens into the env dict without touching os.environ."""
    if not claude_token and not git_token:
        return env
    merged: dict[str, str] = dict(env) if env is not None else {}
    if claude_token:
        merged[ENV_KEY_CLAUDE_TOKEN] = claude_token
    if git_token:
        merged[ENV_KEY_GIT_TOKEN] = git_token
    return merged


async def _restart_terminal_run(server: "AgentServer", body: ResumeRequest) -> dict:
    """Restart a stopped/crashed/completed run by re-bootstrapping from its branch."""
    run_id = body.run_id
    run_info = await db.get_run_for_resume(run_id)
    if not run_info:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run_info["branch_name"]:
        raise HTTPException(status_code=409, detail="Run has no branch — cannot resume")

    prompt = body.prompt or run_info["custom_prompt"]
    if not prompt:
        raise HTTPException(status_code=409, detail="Run has no prompt and none provided")
    github_repo = body.github_repo or run_info["github_repo"]
    if not github_repo:
        raise HTTPException(status_code=409, detail="Run has no github_repo")
    if not run_info["model_name"]:
        raise HTTPException(status_code=409, detail="Run has no model_name in DB")
    if not run_info["base_branch"]:
        raise HTTPException(status_code=409, detail="Run has no base_branch in DB")

    merged_env = _merge_tokens_into_env(body.env, body.claude_token, body.git_token)
    start_body = StartRequest(
        prompt=prompt,
        max_budget_usd=0,
        duration_minutes=run_info["duration_minutes"],
        base_branch=run_info["base_branch"],
        model=run_info["model_name"],
        github_repo=github_repo,
        env=merged_env,
    )

    # Clean up stale ActiveRun if present (e.g. crashed but not cleaned up).
    server.remove_run(run_id)

    active = ActiveRun(run_id=run_id)
    server.register_run(active)

    task = asyncio.create_task(server.execute_run(active, start_body))
    active.task = task
    task.add_done_callback(lambda t: server.on_task_done(active, t))
    return {"ok": True, "event": "resume", "run_id": run_id, "restarted": True}


def register_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register all HTTP route handlers on the FastAPI app."""

    @app.get("/health")
    async def health() -> HealthResponse:
        """Agent health with per-run details."""
        runs_list: list[HealthRunEntry] = []
        for r in server.runs().values():
            if not r.run_id:
                continue
            entry = HealthRunEntry(
                run_id=r.run_id,
                status=r.status,
                started_at=r.started_at,
            )
            if r.time_lock:
                entry.elapsed_minutes = round(r.time_lock.elapsed_minutes(), 1)
                entry.time_remaining = r.time_lock.time_remaining_str()
                entry.run_unlocked = not r.time_lock.locked
            runs_list.append(entry)
        return HealthResponse(
            status="running" if server.active_count() > 0 else "idle",
            active_runs=server.active_count(),
            max_concurrent=MAX_CONCURRENT_RUNS,
            runs=runs_list,
        )

    @app.post("/start")
    async def start_run(body: StartRequest):
        """Start a new run — bootstraps a sandbox and kicks off the round loop."""
        server.ensure_capacity()

        body.env = _merge_tokens_into_env(
            body.env,
            body.claude_token,
            body.git_token,
        )

        if not body.github_repo:
            raise HTTPException(
                status_code=422,
                detail="github_repo is required",
            )
        if not body.prompt:
            raise HTTPException(
                status_code=422,
                detail="prompt is required — AutoFyn needs a task",
            )

        run_id = str(uuid.uuid4())
        await db.create_run_starting(
            run_id,
            body.prompt,
            body.duration_minutes,
            body.base_branch,
            body.github_repo,
            body.model,
        )

        active = ActiveRun(run_id=run_id)
        server.register_run(active)

        task = asyncio.create_task(server.execute_run(active, body))
        active.task = task
        task.add_done_callback(lambda t: server.on_task_done(active, t))
        return {"ok": True, "status": "starting", "run_id": run_id}

    # ── Control Signals ────────────────────────────────────────────────

    @app.post("/stop")
    async def stop(body: StopRequest, run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.skip_pr = body.skip_pr
        r.inbox.push("stop", "User stop via API")
        return {"ok": True, "event": "stop", "run_id": r.run_id}

    @app.post("/pause")
    async def pause(run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("pause", "")
        return {"ok": True, "event": "pause", "run_id": r.run_id}

    @app.post("/resume")
    async def resume(body: ResumeRequest | None = None, run_id: str | None = None):
        """Unpause a paused run or restart a terminal run."""
        # If body has run_id, this is a restart of a terminal run.
        if body and body.run_id:
            return await _restart_terminal_run(server, body)

        # Otherwise, unpause a paused run.
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("resume", "")
        return {"ok": True, "event": "resume", "run_id": r.run_id}

    @app.post("/inject")
    async def inject(body: InjectRequest, run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.inbox:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.inbox.push("inject", body.payload or "")
        return {"ok": True, "event": "inject", "run_id": r.run_id}

    @app.post("/unlock")
    async def unlock(run_id: str | None = None):
        r = server.get_run_or_first(run_id)
        if not r.time_lock:
            raise HTTPException(status_code=409, detail="Run not accepting signals")
        r.time_lock.unlock()
        await db.log_audit(r.run_id, "run_unlocked", {})
        if r.inbox:
            r.inbox.push("unlock", "")
        return {"ok": True, "event": "unlock", "run_id": r.run_id}

    @app.post("/cleanup")
    async def cleanup():
        terminal = {
            "completed",
            "completed_no_changes",
            "stopped",
            "error",
            "crashed",
            "killed",
            "rate_limited",
        }
        to_remove = [rid for rid, r in server.runs().items() if r.status in terminal]
        for rid in to_remove:
            del server.runs()[rid]
        return {"ok": True, "cleaned": len(to_remove)}

    # ── Logs ───────────────────────────────────────────────────────────

    @app.get("/logs")
    async def get_logs(tail: int, run_id: str | None = None):
        """Return agent container logs, optionally filtered by run_id.

        Log lines from the agent use run_id[:8] as prefix, e.g.
        ``[abc12345] Round 1 begin``. Continuation lines (tracebacks)
        lack the prefix but belong to the preceding log entry — they
        are included when the parent line matched.

        A line is a "new entry" if it starts with ``[`` (our log format)
        or a timestamp digit. Everything else is a continuation.
        """
        lines = await server.pool().get_self_logs(tail)
        if run_id:
            prefix = run_id[:RUN_ID_LOG_PREFIX_LEN]
            filtered: list[str] = []
            keep = False
            for line in lines:
                if line and (line[0] == "[" or line[0].isdigit()):
                    keep = prefix in line
                if keep:
                    filtered.append(line)
            lines = filtered
        return {"lines": lines, "total": len(lines)}

    # ── Branches (GitHub API proxy) ────────────────────────────────────

    # ── File Diff ──────────────────────────────────────────────────────

    @app.get("/file/diff")
    async def file_diff(
        run_id: str,
        path: str,
        branch: str,
        base: str,
        repo: str,
        token: str,
    ):
        """Per-file unified diff. Tries sandbox first (active run), falls back to GitHub API."""
        # Active run: proxy to sandbox
        client = server.pool().get_client(run_id)
        if client:
            try:
                return await client.repo.file_diff(path)
            except Exception as exc:
                log.warning("Sandbox file/diff failed for %s: %s", run_id, exc)

        # Completed run: GitHub compare API
        url = f"https://api.github.com/repos/{repo}/compare/{base}...{branch}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.diff",
        }
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(url, headers=headers)

        if resp.status_code == 404:
            # Branch deleted — try finding a PR
            pr_url = f"https://api.github.com/repos/{repo}/pulls"
            pr_headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            }
            async with httpx.AsyncClient(timeout=15) as http:
                pr_resp = await http.get(
                    pr_url,
                    headers=pr_headers,
                    params={"head": f"{repo.split('/')[0]}:{branch}", "state": "all", "per_page": 1},
                )
            if pr_resp.status_code == 200 and pr_resp.json():
                pr_number = pr_resp.json()[0]["number"]
                diff_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
                async with httpx.AsyncClient(timeout=15) as http:
                    diff_resp = await http.get(
                        diff_url,
                        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.diff"},
                    )
                if diff_resp.status_code == 200:
                    return _to_patch_response(diff_resp.text, path)
            raise HTTPException(
                status_code=404,
                detail="Branch deleted and no PR found — diff unavailable",
            )

        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"GitHub API error: {resp.text[:200]}",
            )

        return _to_patch_response(resp.text, path)

    @app.get("/branches")
    async def list_branches(repo: str, token: str):
        """List branches on the GitHub remote for the given repo.

        Called by the dashboard's StartRunModal to populate the "branch from"
        dropdown. The dashboard passes the git token it has in settings; we
        just proxy to the GitHub API. No sandbox needed because this runs
        before any run has started.
        """
        if "/" not in repo:
            raise HTTPException(status_code=400, detail="repo must be owner/name")
        url = f"https://api.github.com/repos/{repo}/branches"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers, params={"per_page": 100})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"GitHub API error: {resp.text[:200]}",
            )
        data = resp.json()
        return [b["name"] for b in data if isinstance(b, dict) and "name" in b]
