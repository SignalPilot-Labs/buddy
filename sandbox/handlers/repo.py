"""Repo HTTP handlers for the sandbox.

Three endpoints map to the three fixed phases of an agent run. Each
endpoint bundles every git/gh operation that phase needs into a single
round-trip, so the agent container never has to sequence primitives.

Endpoints:
    POST /repo/bootstrap   clone + verify base + create working branch
    POST /repo/save        commit + push per-round changes (no-op if clean)
    POST /repo/teardown    commit leftovers + push + PR + diff stats

Auth is installed at bootstrap: `GIT_TOKEN` + `GH_TOKEN` are set in the
sandbox process env, and git's global credential helper is configured to
read `$GIT_TOKEN` at request time. Every subsequent git/gh command — from
the handlers in this file or from subagent-spawned shells — picks up auth
transparently. Nothing is written to disk.

Security rules (enforced here because they protect against orchestrator
bugs — not malicious subagents, which gVisor + SDK SecurityGate handle):
    1. Working branch is set by bootstrap and never changes. `save` and
       `teardown` refuse if HEAD doesn't match it.
    2. Push is always `push -u origin <working_branch>` — no refspec,
       no other target.
    3. PR create/update always uses the working branch as head.
"""

import asyncio
import json
import logging
import os
import subprocess

from aiohttp import web

from constants import (
    GIT_CREDENTIAL_HELPER,
    REPO_BRANCH_NAME_MAX_LEN,
    REPO_BRANCH_NAME_PATTERN,
    REPO_WORK_DIR,
)
from models import CmdResult, RepoState

log = logging.getLogger("sandbox.endpoints.repo")


def _state(request: web.Request) -> RepoState:
    """Fetch RepoState. Fails fast if the repo hasn't been bootstrapped yet."""
    state = request.app.get("repo_state")
    if state is None:
        raise web.HTTPConflict(
            reason="repo not bootstrapped — call /repo/bootstrap first",
        )
    return state


# ── Validation ───────────────────────────────────────────────────────


def _validate_branch(name: str) -> None:
    """Reject branch names that could smuggle shell metacharacters."""
    if not name or len(name) > REPO_BRANCH_NAME_MAX_LEN:
        raise web.HTTPBadRequest(reason=f"invalid branch length: {len(name or '')}")
    if not REPO_BRANCH_NAME_PATTERN.match(name):
        raise web.HTTPBadRequest(reason="invalid branch name characters")
    if ".." in name or name.endswith(".lock") or name.endswith("/"):
        raise web.HTTPBadRequest(reason="invalid branch name format")


# ── Subprocess helpers ───────────────────────────────────────────────


async def _run(args: list[str], cwd: str, timeout: int) -> CmdResult:
    """Run a subprocess inheriting the sandbox process env."""
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return CmdResult(
            stdout=(stdout or b"").decode(),
            stderr=(stderr or b"").decode(),
            exit_code=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
        return CmdResult(stdout="", stderr="timed out", exit_code=-1)


async def _git(args: list[str], timeout: int, cwd: str = REPO_WORK_DIR) -> CmdResult:
    """Run `git <args>`. Callers inspect exit_code themselves."""
    return await _run(["git"] + args, cwd, timeout)


async def _gh(args: list[str], timeout: int, cwd: str = REPO_WORK_DIR) -> CmdResult:
    """Run `gh <args>`."""
    return await _run(["gh"] + args, cwd, timeout)


def _fail(result: CmdResult, label: str) -> None:
    """Raise HTTP 500 with the git/gh error in the JSON body on failure.

    Stderr goes into the body (not the HTTP reason header) because
    aiohttp rejects reason values containing `\\r` or `\\n`, and git
    stderr routinely contains newlines.
    """
    if result.exit_code != 0:
        stderr = result.stderr.strip()[:2000]
        log.error("%s failed (exit=%d): %s", label, result.exit_code, stderr)
        body = json.dumps({
            "error": f"{label} failed",
            "exit_code": result.exit_code,
            "stderr": stderr,
        })
        raise web.HTTPInternalServerError(
            text=body,
            content_type="application/json",
        )


async def _install_git_credentials(token: str, timeout: int) -> None:
    """Install the token so every git/gh command authenticates transparently.

    Sets `GIT_TOKEN` + `GH_TOKEN` in the process env and configures git's
    global credential helper to read `$GIT_TOKEN` at request time. Nothing
    on disk — the secret lives in process memory only and is inherited by
    subagent-spawned shells that need authenticated git operations.
    """
    os.environ["GIT_TOKEN"] = token
    os.environ["GH_TOKEN"] = token

    cfg = await _git(
        ["config", "--global", "credential.helper", GIT_CREDENTIAL_HELPER],
        timeout, cwd="/",
    )
    _fail(cfg, "git config credential.helper")


# ── Private git op helpers (called by handlers below) ────────────────


async def _require_on_working_branch(state: RepoState, timeout: int) -> None:
    """Refuse if HEAD isn't on the expected working branch."""
    current = await _git(["branch", "--show-current"], timeout)
    head = current.stdout.strip()
    if head != state.working_branch:
        raise web.HTTPConflict(
            reason=f"HEAD is on '{head}', not working branch '{state.working_branch}'",
        )


async def _has_changes(timeout: int) -> bool:
    """True if the working tree has uncommitted or staged changes."""
    result = await _git(["status", "--porcelain"], timeout)
    _fail(result, "git status")
    return bool(result.stdout.strip())


async def _commit(message: str, timeout: int) -> bool:
    """Stage everything and commit. Returns True on commit, False if clean."""
    _fail(await _git(["add", "."], timeout), "git add")
    result = await _git(["commit", "-m", message], timeout)
    if result.exit_code != 0 and "nothing to commit" in (result.stdout + result.stderr):
        return False
    _fail(result, "git commit")
    return True


async def _push(working_branch: str, timeout: int) -> str | None:
    """Push working branch to origin. Returns error string on failure, None on success."""
    result = await _git(["push", "-u", "origin", working_branch], timeout)
    if result.exit_code != 0:
        err = result.stderr.strip()[:500]
        log.warning("push failed: %s", err)
        return err
    return None


async def _commits_ahead(base: str, timeout: int) -> int:
    """Count commits between origin/base and HEAD."""
    _fail(
        await _git(["fetch", "origin", base, "--depth", "1"], timeout),
        "git fetch base",
    )
    result = await _git(
        ["rev-list", "--count", f"origin/{base}..HEAD"], timeout,
    )
    _fail(result, "git rev-list")
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


async def _branch_diff(
    working_branch: str, base: str, timeout: int,
) -> list[dict]:
    """File-level diff stats between the working branch and base."""
    await _git(["fetch", "origin", base, "--depth", "1"], timeout)
    numstat = await _git(
        ["diff", "--numstat", f"origin/{base}...{working_branch}"], timeout,
    )
    if numstat.exit_code != 0 or not numstat.stdout.strip():
        return []
    name_status = await _git(
        ["diff", "--name-status", f"origin/{base}...{working_branch}"], timeout,
    )
    if name_status.exit_code != 0:
        return []
    return _parse_numstat(numstat.stdout, _parse_name_status(name_status.stdout))


async def _create_or_update_pr(
    state: RepoState, title: str, description: str, base: str, timeout: int,
) -> tuple[str | None, str | None]:
    """Create a PR, or edit the existing one. Returns (url, error)."""
    find = await _gh(
        ["pr", "view", state.working_branch, "--repo", state.repo,
         "--json", "url", "-q", ".url"],
        timeout,
    )
    existing = find.stdout.strip() if find.exit_code == 0 else ""

    if existing:
        edit = await _gh(
            ["pr", "edit", existing, "--title", title, "--body", description],
            timeout,
        )
        if edit.exit_code != 0:
            return existing, f"gh pr edit failed: {edit.stderr.strip()[:200]}"
        return existing, None

    create = await _gh(
        [
            "pr", "create",
            "--repo", state.repo,
            "--base", base,
            "--head", state.working_branch,
            "--title", title,
            "--body", description,
        ],
        timeout,
    )
    if create.exit_code != 0:
        return None, f"gh pr create failed: {create.stderr.strip()[:200]}"
    return create.stdout.strip(), None


# ── Handler: /repo/bootstrap ─────────────────────────────────────────


async def handle_bootstrap(request: web.Request) -> web.Response:
    """Clone the repo, verify the base branch exists, create the working
    branch. One round-trip for the entire setup phase.

    This is the only handler that constructs `RepoState`. All other
    endpoints require it to exist and fail fast otherwise.
    """
    body = await request.json()
    repo: str = body["repo"]
    token: str = body["token"]
    base_branch: str = body["base_branch"]
    working_branch: str = body["working_branch"]
    timeout: int = body["timeout"]

    if "/" not in repo:
        raise web.HTTPBadRequest(reason="repo must be owner/name")
    _validate_branch(base_branch)
    _validate_branch(working_branch)

    await _install_git_credentials(token, timeout)

    await _run(["rm", "-rf", REPO_WORK_DIR], "/", timeout)
    await _run(["mkdir", "-p", REPO_WORK_DIR], "/", timeout)

    remote_url = f"https://github.com/{repo}.git"
    _fail(
        await _git(
            ["clone", "--depth", "50", "--no-single-branch", remote_url, "."],
            timeout,
        ),
        "git clone",
    )

    _fail(
        await _git(
            ["ls-remote", "--exit-code", "--heads", "origin", base_branch],
            timeout,
        ),
        f"base branch '{base_branch}' not found on origin",
    )

    for args in (
        ["fetch", "origin", base_branch],
        ["checkout", "-B", base_branch, f"origin/{base_branch}"],
        ["checkout", "-b", working_branch],
    ):
        _fail(await _git(args, timeout), f"git {args[0]}")

    request.app["repo_state"] = RepoState(
        repo=repo,
        base_branch=base_branch,
        working_branch=working_branch,
    )
    return web.json_response({
        "ok": True,
        "working_branch": working_branch,
    })


# ── Handler: /repo/save ──────────────────────────────────────────────


async def handle_save(request: web.Request) -> web.Response:
    """Per-round commit + push. No-op if the working tree is clean.

    Returns a structured result so the caller can decide how to react to
    a failed push (typically: log it and move on to the next round).
    """
    state = _state(request)
    body = await request.json()
    message: str = body["message"]
    timeout: int = body["timeout"]

    await _require_on_working_branch(state, timeout)

    if not await _has_changes(timeout):
        return web.json_response({
            "committed": False,
            "pushed": False,
            "push_error": None,
        })

    committed = await _commit(message, timeout)
    if not committed:
        return web.json_response({
            "committed": False,
            "pushed": False,
            "push_error": None,
        })

    push_error = await _push(state.working_branch, timeout)
    return web.json_response({
        "committed": True,
        "pushed": push_error is None,
        "push_error": push_error,
    })


# ── Handler: /repo/teardown ──────────────────────────────────────────


async def handle_teardown(request: web.Request) -> web.Response:
    """End-of-run: commit leftovers, push, create/update PR, capture diff.

    Returns a structured result describing what happened at each stage.
    Non-fatal errors (push failure, PR failure) are reported in the body
    rather than raised, so the caller always gets diff stats back.
    """
    state = _state(request)
    body = await request.json()
    pr_title: str = body["pr_title"]
    pr_description: str = body["pr_description"]
    base: str = body["base"]
    timeout: int = body["timeout"]
    _validate_branch(base)

    await _require_on_working_branch(state, timeout)

    auto_committed = False
    if await _has_changes(timeout):
        auto_committed = await _commit(
            "Auto-commit: save uncommitted work at session end", timeout,
        )

    ahead = await _commits_ahead(base, timeout)
    if ahead == 0:
        diff = await _branch_diff(state.working_branch, base, timeout)
        return web.json_response({
            "auto_committed": auto_committed,
            "commits_ahead": 0,
            "pushed": False,
            "push_error": None,
            "pr_url": None,
            "pr_error": None,
            "diff_stats": diff,
        })

    push_error = await _push(state.working_branch, timeout)
    if push_error is not None:
        diff = await _branch_diff(state.working_branch, base, timeout)
        return web.json_response({
            "auto_committed": auto_committed,
            "commits_ahead": ahead,
            "pushed": False,
            "push_error": push_error,
            "pr_url": None,
            "pr_error": None,
            "diff_stats": diff,
        })

    pr_url, pr_error = await _create_or_update_pr(
        state, pr_title, pr_description, base, timeout,
    )
    diff = await _branch_diff(state.working_branch, base, timeout)
    return web.json_response({
        "auto_committed": auto_committed,
        "commits_ahead": ahead,
        "pushed": True,
        "push_error": None,
        "pr_url": pr_url,
        "pr_error": pr_error,
        "diff_stats": diff,
    })


# ── Parse helpers ────────────────────────────────────────────────────


def _parse_name_status(raw: str) -> dict[str, str]:
    """Parse `git diff --name-status` into a path->status map."""
    result: dict[str, str] = {}
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            code = parts[0][0]
            result[parts[-1]] = {
                "A": "added", "M": "modified",
                "D": "deleted", "R": "renamed",
            }.get(code, "modified")
    return result


def _parse_numstat(raw: str, status_map: dict[str, str]) -> list[dict]:
    """Parse `git diff --numstat` into file change dicts."""
    results: list[dict] = []
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        results.append({
            "path": parts[2],
            "added": int(parts[0]) if parts[0] != "-" else 0,
            "removed": int(parts[1]) if parts[1] != "-" else 0,
            "status": status_map.get(parts[2], "modified"),
        })
    return results


# ── Registration ─────────────────────────────────────────────────────


def register(app: web.Application) -> None:
    """Attach /repo/bootstrap, /repo/save, /repo/teardown routes."""
    app.router.add_post("/repo/bootstrap", handle_bootstrap)
    app.router.add_post("/repo/save", handle_save)
    app.router.add_post("/repo/teardown", handle_teardown)
