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
    CMD_TIMEOUT,
    GIT_CREDENTIAL_HELPER,
    REPO_BRANCH_NAME_MAX_LEN,
    REPO_BRANCH_NAME_PATTERN,
    REPO_WORK_DIR,
    RETRY_BASE_DELAY_SEC,
    RETRY_MAX_ATTEMPTS,
    RETRY_TRANSIENT_PATTERNS,
)
from handlers.repo_parse import _normalize_rename_path, _parse_name_status, _parse_numstat
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


async def _with_retry(cmd: list[str], cwd: str, timeout: int) -> CmdResult:
    """Run a command with exponential backoff on transient failures."""
    result = CmdResult(stdout="", stderr="", exit_code=-1)
    for attempt in range(RETRY_MAX_ATTEMPTS):
        result = await _run(cmd, cwd, timeout)
        if result.exit_code == 0:
            return result
        if not any(p in result.stderr.lower() for p in RETRY_TRANSIENT_PATTERNS):
            return result
        if attempt < RETRY_MAX_ATTEMPTS - 1:
            delay = RETRY_BASE_DELAY_SEC * (2 ** attempt)
            log.warning("%s: transient error, retry %d/%d in %.0fs", cmd[0], attempt + 1, RETRY_MAX_ATTEMPTS, delay)
            await asyncio.sleep(delay)
    return result


async def _git(args: list[str], timeout: int, cwd: str = REPO_WORK_DIR) -> CmdResult:
    """Run `git <args>` with retry on transient network errors."""
    return await _with_retry(["git"] + args, cwd, timeout)


async def _gh(args: list[str], timeout: int, cwd: str = REPO_WORK_DIR) -> CmdResult:
    """Run `gh <args>` with retry on transient network errors."""
    return await _with_retry(["gh"] + args, cwd, timeout)


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
    working_branch: str, base_sha: str, timeout: int,
) -> list[dict]:
    """File-level diff stats between the working branch and the base-point SHA.

    `base_sha` is captured once at bootstrap from `origin/<base_branch>`
    and stored on `RepoState`. Diffing against it (rather than the
    current `origin/<base>` tip) means:

    - Only changes the branch introduced are surfaced. Base commits
      merged in after the branch started don't appear as 'deletions'
      from the branch's perspective.
    - No extra network fetch per call — the SHA is already in the
      local object DB from bootstrap.

    Two-arg form (`git diff A B`) is used so no merge base is required,
    unaffected by shallow fetches or force-updated bases.
    """
    numstat = await _git(["diff", "--numstat", base_sha, working_branch], timeout)
    if numstat.exit_code != 0 or not numstat.stdout.strip():
        return []
    name_status = await _git(
        ["diff", "--name-status", base_sha, working_branch], timeout,
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

    # Clone into a temp dir first, then merge into REPO_WORK_DIR.
    # Host bind mounts may already exist under REPO_WORK_DIR, making
    # it non-empty. rm -rf can't remove mount points, and git clone
    # refuses non-empty dirs. Cloning to /tmp then cp -a works because
    # cp merges into existing dirs without touching mount points.
    clone_tmp = "/tmp/repo-clone"
    await _run(["rm", "-rf", clone_tmp], "/", timeout)
    await _run(["mkdir", "-p", clone_tmp], "/", timeout)
    await _run(["rm", "-rf", REPO_WORK_DIR], "/", timeout)
    await _run(["mkdir", "-p", REPO_WORK_DIR], "/", timeout)

    remote_url = f"https://github.com/{repo}.git"
    _fail(
        await _git(
            ["clone", "--depth", "50", "--no-single-branch", remote_url, "."],
            timeout,
            cwd=clone_tmp,
        ),
        "git clone",
    )

    # After rm -rf + mkdir, any surviving entries in REPO_WORK_DIR are
    # bind mount points (Docker protects them). The user's mounted data
    # takes precedence over repo contents — skip those dirs during copy.
    mount_entries = await _run(["ls", "-A", REPO_WORK_DIR], "/", timeout)
    excludes = [
        name.strip() for name in mount_entries.stdout.strip().split("\n") if name.strip()
    ]
    rsync_cmd = ["rsync", "-a"]
    for name in excludes:
        log.warning("Host mount shadows repo dir '%s' — using mounted version", name)
        rsync_cmd.append(f"--exclude=/{name}")
    rsync_cmd += [f"{clone_tmp}/", f"{REPO_WORK_DIR}/"]
    _fail(await _run(rsync_cmd, "/", timeout), "rsync clone into repo dir")
    await _run(["rm", "-rf", clone_tmp], "/", timeout)

    _fail(
        await _git(
            ["ls-remote", "--exit-code", "--heads", "origin", base_branch],
            timeout,
        ),
        f"base branch '{base_branch}' not found on origin",
    )

    _fail(await _git(["fetch", "origin", base_branch], timeout), "git fetch")
    _fail(
        await _git(["checkout", "-B", base_branch, f"origin/{base_branch}"], timeout),
        "git checkout base",
    )

    # Freeze the base SHA now. Every subsequent diff (teardown stats,
    # live /repo/diff/stats) uses this SHA — independent of base moving on.
    sha_result = await _git(["rev-parse", f"origin/{base_branch}"], timeout)
    _fail(sha_result, f"git rev-parse origin/{base_branch}")
    base_sha = sha_result.stdout.strip()
    if not base_sha:
        raise web.HTTPInternalServerError(
            reason=f"git rev-parse origin/{base_branch} returned empty SHA",
        )

    # Resume: if the working branch already exists on origin, check it out.
    # Fresh run: create a new branch from base.
    ls_result = await _git(
        ["ls-remote", "--exit-code", "--heads", "origin", working_branch], timeout,
    )
    if ls_result.exit_code == 0:
        _fail(await _git(["fetch", "origin", working_branch], timeout), "git fetch working branch")
        _fail(
            await _git(["checkout", "-b", working_branch, f"origin/{working_branch}"], timeout),
            "git checkout existing branch",
        )
    else:
        _fail(await _git(["checkout", "-b", working_branch], timeout), "git checkout -b")

    request.app["repo_state"] = RepoState(
        repo=repo,
        base_branch=base_branch,
        working_branch=working_branch,
        base_sha=base_sha,
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
        diff = await _branch_diff(state.working_branch, state.base_sha, timeout)
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
        diff = await _branch_diff(state.working_branch, state.base_sha, timeout)
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


async def handle_diff(request: web.Request) -> web.Response:
    """Return the full unified diff of the working branch against base.

    Diff target is the base-point SHA captured at bootstrap — stable even
    if `origin/<base>` has since advanced or been force-updated.
    """
    state = _state(request)
    if not state.working_branch or not state.base_branch:
        return web.json_response({"error": "No active branch"}, status=409)

    result = await _git(
        ["diff", state.base_sha, state.working_branch], CMD_TIMEOUT,
    )
    if result.exit_code != 0:
        return web.json_response({"error": "git diff failed", "detail": result.stderr[:500]}, status=500)
    return web.json_response({"diff": result.stdout})


async def handle_diff_stats(request: web.Request) -> web.Response:
    """Return per-file diff stats without transferring the full diff body.

    Used by the dashboard Changes panel on every poll (~every 15s). The
    full-diff endpoint streams megabytes; this one returns a few hundred
    bytes derived from `git diff --numstat` + `--name-status`.
    """
    state = _state(request)
    if not state.working_branch or not state.base_branch:
        return web.json_response({"error": "No active branch"}, status=409)
    files = await _branch_diff(state.working_branch, state.base_sha, CMD_TIMEOUT)
    return web.json_response({"files": files})


# ── Registration ─────────────────────────────────────────────────────


def register(app: web.Application) -> None:
    """Attach /repo/* routes."""
    app.router.add_post("/repo/bootstrap", handle_bootstrap)
    app.router.add_post("/repo/save", handle_save)
    app.router.add_post("/repo/teardown", handle_teardown)
    app.router.add_post("/repo/diff", handle_diff)
    app.router.add_post("/repo/diff/stats", handle_diff_stats)
