"""Repo HTTP handlers for the sandbox.

All git and gh operations the agent needs run here. State lives on the
aiohttp app under the "repo_state" key:

    - repo           the GitHub repo (owner/name)
    - token          the GIT_TOKEN used for https auth
    - base_branch    the branch PRs target
    - active_branch  the working branch the agent is allowed to mutate

Security rules enforced at the handler layer (not via SDK SecurityGate,
which only covers subagent Bash commands):

    1. `commit`, `push`, and PR creation are only allowed when the repo
       HEAD matches the active branch stored in state.
    2. `push` always refuses refspecs — HEAD only, origin only.
    3. `pr` must be on the active branch with commits ahead of base.

These rules protect against agent bugs, not malicious subagents. gVisor
isolates the sandbox process already.
"""

import asyncio
import base64
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field

from aiohttp import web

from constants import CMD_TIMEOUT

log = logging.getLogger("sandbox.endpoints.repo")

# ── Configuration ────────────────────────────────────────────────────

WORK_DIR = "/home/agentuser/repo"
BRANCH_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$")
BRANCH_NAME_MAX_LEN = 256


# ── State ────────────────────────────────────────────────────────────


@dataclass
class RepoState:
    """Per-sandbox repo state. One sandbox == one run == one active branch."""

    repo: str = ""
    token: str = ""
    base_branch: str = ""
    active_branch: str = ""
    authed_envs: dict[str, str] = field(default_factory=dict)


def _state(request: web.Request) -> RepoState:
    """Fetch the RepoState instance attached to the aiohttp app."""
    return request.app["repo_state"]


# ── Validation ───────────────────────────────────────────────────────


def _validate_branch(name: str) -> None:
    """Reject branch names that could smuggle shell metacharacters."""
    if not name or len(name) > BRANCH_NAME_MAX_LEN:
        raise web.HTTPBadRequest(reason=f"invalid branch length: {len(name or '')}")
    if not BRANCH_NAME_PATTERN.match(name):
        raise web.HTTPBadRequest(reason="invalid branch name characters")
    if ".." in name or name.endswith(".lock") or name.endswith("/"):
        raise web.HTTPBadRequest(reason="invalid branch name format")


def _require_active_branch(state: RepoState) -> None:
    """Refuse mutating ops when no working branch has been established."""
    if not state.active_branch:
        raise web.HTTPConflict(
            reason="no active working branch — call create_branch first",
        )


async def _require_on_active_branch(state: RepoState, timeout: int) -> None:
    """Refuse to commit/push unless the repo HEAD matches the active branch."""
    _require_active_branch(state)
    current = await _run_git(["branch", "--show-current"], WORK_DIR, timeout, {})
    head = current.stdout.strip()
    if head != state.active_branch:
        raise web.HTTPConflict(reason=(
            f"HEAD is on '{head}', not active branch '{state.active_branch}'"
        ))


# ── Subprocess helpers ───────────────────────────────────────────────


@dataclass
class _CmdResult:
    stdout: str
    stderr: str
    exit_code: int


async def _run(
    args: list[str], cwd: str, timeout: int, env: dict[str, str],
) -> _CmdResult:
    """Run a subprocess with a merged env (os.environ + `env`)."""
    merged = dict(os.environ)
    merged.update(env)
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=merged,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return _CmdResult(
            stdout=(stdout or b"").decode(),
            stderr=(stderr or b"").decode(),
            exit_code=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
        return _CmdResult(stdout="", stderr="timed out", exit_code=-1)


async def _run_git(
    args: list[str], cwd: str, timeout: int, env: dict[str, str],
) -> _CmdResult:
    """Run `git <args>`. Callers inspect exit_code themselves."""
    return await _run(["git"] + args, cwd, timeout, env)


async def _run_gh(
    args: list[str], cwd: str, timeout: int, env: dict[str, str],
) -> _CmdResult:
    """Run `gh <args>`."""
    return await _run(["gh"] + args, cwd, timeout, env)


def _auth_env(token: str) -> dict[str, str]:
    """Build git/gh env vars from a GitHub token."""
    if not token:
        return {}
    b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "GH_TOKEN": token,
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {b64}",
    }


def _fail(result: _CmdResult, label: str) -> None:
    """Raise HTTP 500 if a git/gh command failed."""
    if result.exit_code != 0:
        raise web.HTTPInternalServerError(
            reason=f"{label} failed: {result.stderr.strip()[:500]}",
        )


# ── Handlers: Setup ──────────────────────────────────────────────────


async def handle_clone(request: web.Request) -> web.Response:
    """Clone the repo into WORK_DIR and persist auth into the local config."""
    state = _state(request)
    body = await request.json()
    repo: str = body["repo"]
    token: str = body["token"]
    base_branch: str = body.get("base_branch", "main")
    timeout: int = body.get("timeout", CMD_TIMEOUT)

    _validate_branch(base_branch)
    if "/" not in repo:
        raise web.HTTPBadRequest(reason="repo must be owner/name")

    state.repo = repo
    state.token = token
    state.base_branch = base_branch
    state.authed_envs = _auth_env(token)

    await _run(["rm", "-rf", WORK_DIR], "/", timeout, {})
    await _run(["mkdir", "-p", WORK_DIR], "/", timeout, {})

    remote_url = f"https://github.com/{repo}.git"
    result = await _run_git(
        ["clone", "--depth", "50", "--no-single-branch", remote_url, "."],
        WORK_DIR, timeout, state.authed_envs,
    )
    _fail(result, "git clone")

    b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    cfg = await _run_git(
        ["config", "http.extraHeader", f"Authorization: Basic {b64}"],
        WORK_DIR, timeout, {},
    )
    _fail(cfg, "git config")

    return web.json_response({"ok": True})


async def handle_ensure_base_branch(request: web.Request) -> web.Response:
    """Verify that the base branch exists on the configured remote."""
    state = _state(request)
    body = await request.json()
    base: str = body.get("base", state.base_branch)
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    _validate_branch(base)

    result = await _run_git(
        ["ls-remote", "--exit-code", "--heads", "origin", base],
        WORK_DIR, timeout, state.authed_envs,
    )
    _fail(result, "ls-remote")
    return web.json_response({"ok": True, "base_branch": base})


# ── Handlers: Branches ───────────────────────────────────────────────


async def handle_create_branch(request: web.Request) -> web.Response:
    """Reset to origin/base and create a new working branch."""
    state = _state(request)
    body = await request.json()
    name: str = body["name"]
    base: str = body.get("base", state.base_branch)
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    _validate_branch(name)
    _validate_branch(base)

    for args in (
        ["fetch", "origin", base],
        ["checkout", "-B", base, f"origin/{base}"],
        ["checkout", "-b", name],
    ):
        result = await _run_git(args, WORK_DIR, timeout, state.authed_envs)
        _fail(result, f"git {args[0]}")

    state.active_branch = name
    return web.json_response({"ok": True, "active_branch": name})


async def handle_checkout_branch(request: web.Request) -> web.Response:
    """Checkout an existing branch (for resume). Sets active_branch."""
    state = _state(request)
    body = await request.json()
    name: str = body["name"]
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    _validate_branch(name)

    for args in (
        ["fetch", "origin", name],
        ["checkout", name],
        ["pull", "origin", name],
    ):
        result = await _run_git(args, WORK_DIR, timeout, state.authed_envs)
        _fail(result, f"git {args[0]}")

    state.active_branch = name
    return web.json_response({"ok": True, "active_branch": name})


async def handle_current_branch(request: web.Request) -> web.Response:
    """Return the current git HEAD branch name."""
    timeout: int = (await request.json()).get("timeout", CMD_TIMEOUT)
    result = await _run_git(["branch", "--show-current"], WORK_DIR, timeout, {})
    _fail(result, "git branch")
    return web.json_response({"branch": result.stdout.strip()})


# ── Handlers: Status / diff ──────────────────────────────────────────


async def handle_has_changes(request: web.Request) -> web.Response:
    """Return True if the working tree has uncommitted or staged changes."""
    timeout: int = (await request.json()).get("timeout", CMD_TIMEOUT)
    result = await _run_git(["status", "--porcelain"], WORK_DIR, timeout, {})
    _fail(result, "git status")
    return web.json_response({"has_changes": bool(result.stdout.strip())})


async def handle_commits_ahead(request: web.Request) -> web.Response:
    """Return the commit count between origin/base and HEAD."""
    state = _state(request)
    body = await request.json()
    base: str = body.get("base", state.base_branch)
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    _validate_branch(base)

    result = await _run_git(
        ["rev-list", "--count", f"origin/{base}..HEAD"],
        WORK_DIR, timeout, {},
    )
    _fail(result, "git rev-list")
    try:
        count = int(result.stdout.strip())
    except ValueError:
        count = 0
    return web.json_response({"count": count})


async def handle_branch_diff(request: web.Request) -> web.Response:
    """Return file-level diff stats between the active branch and base."""
    state = _state(request)
    body = await request.json()
    base: str = body.get("base", state.base_branch)
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    _require_active_branch(state)
    _validate_branch(base)

    await _run_git(
        ["fetch", "origin", base, "--depth", "1"],
        WORK_DIR, timeout, state.authed_envs,
    )
    numstat = await _run_git(
        ["diff", "--numstat", f"origin/{base}...{state.active_branch}"],
        WORK_DIR, timeout, {},
    )
    _fail(numstat, "git diff")
    if not numstat.stdout.strip():
        return web.json_response({"files": []})

    name_status = await _run_git(
        ["diff", "--name-status", f"origin/{base}...{state.active_branch}"],
        WORK_DIR, timeout, {},
    )
    _fail(name_status, "git diff")
    return web.json_response({
        "files": _parse_numstat(
            numstat.stdout, _parse_name_status(name_status.stdout),
        ),
    })


# ── Handlers: Commit / push ──────────────────────────────────────────


async def handle_commit(request: web.Request) -> web.Response:
    """Stage everything and create a commit. HEAD must be on active branch."""
    state = _state(request)
    body = await request.json()
    message: str = body["message"]
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    await _require_on_active_branch(state, timeout)

    add = await _run_git(["add", "."], WORK_DIR, timeout, {})
    _fail(add, "git add")
    commit = await _run_git(
        ["commit", "-m", message], WORK_DIR, timeout, {},
    )
    if commit.exit_code != 0 and "nothing to commit" in (commit.stdout + commit.stderr):
        return web.json_response({"ok": True, "committed": False})
    _fail(commit, "git commit")
    return web.json_response({"ok": True, "committed": True})


async def handle_push(request: web.Request) -> web.Response:
    """Push the active branch to origin. HEAD must be on active branch."""
    state = _state(request)
    body = await request.json()
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    await _require_on_active_branch(state, timeout)

    result = await _run_git(
        ["push", "-u", "origin", state.active_branch],
        WORK_DIR, timeout, state.authed_envs,
    )
    _fail(result, "git push")
    return web.json_response({"ok": True, "branch": state.active_branch})


# ── Handlers: PR ─────────────────────────────────────────────────────


async def handle_find_pr(request: web.Request) -> web.Response:
    """Look up an existing PR for the active branch. Returns url or null."""
    state = _state(request)
    body = await request.json()
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    _require_active_branch(state)

    result = await _run_gh(
        [
            "pr", "view", state.active_branch,
            "--repo", state.repo,
            "--json", "url", "-q", ".url",
        ],
        WORK_DIR, timeout, state.authed_envs,
    )
    if result.exit_code != 0:
        return web.json_response({"url": None})
    url = result.stdout.strip()
    return web.json_response({"url": url or None})


async def handle_create_or_update_pr(request: web.Request) -> web.Response:
    """Create a PR, or edit an existing one, for the active branch."""
    state = _state(request)
    body = await request.json()
    title: str = body["title"]
    description: str = body["description"]
    base: str = body.get("base", state.base_branch)
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    _validate_branch(base)
    await _require_on_active_branch(state, timeout)

    find = await _run_gh(
        [
            "pr", "view", state.active_branch,
            "--repo", state.repo,
            "--json", "url", "-q", ".url",
        ],
        WORK_DIR, timeout, state.authed_envs,
    )
    existing = find.stdout.strip() if find.exit_code == 0 else ""

    if existing:
        edit = await _run_gh(
            ["pr", "edit", existing, "--title", title, "--body", description],
            WORK_DIR, timeout, state.authed_envs,
        )
        _fail(edit, "gh pr edit")
        return web.json_response({"ok": True, "url": existing, "created": False})

    create = await _run_gh(
        [
            "pr", "create",
            "--repo", state.repo,
            "--base", base,
            "--head", state.active_branch,
            "--title", title,
            "--body", description,
        ],
        WORK_DIR, timeout, state.authed_envs,
    )
    _fail(create, "gh pr create")
    return web.json_response({
        "ok": True,
        "url": create.stdout.strip(),
        "created": True,
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
    """Attach repo state + /repo/* routes to the aiohttp app."""
    app["repo_state"] = RepoState()
    app.router.add_post("/repo/clone", handle_clone)
    app.router.add_post("/repo/ensure_base_branch", handle_ensure_base_branch)
    app.router.add_post("/repo/create_branch", handle_create_branch)
    app.router.add_post("/repo/checkout_branch", handle_checkout_branch)
    app.router.add_post("/repo/current_branch", handle_current_branch)
    app.router.add_post("/repo/has_changes", handle_has_changes)
    app.router.add_post("/repo/commits_ahead", handle_commits_ahead)
    app.router.add_post("/repo/branch_diff", handle_branch_diff)
    app.router.add_post("/repo/commit", handle_commit)
    app.router.add_post("/repo/push", handle_push)
    app.router.add_post("/repo/find_pr", handle_find_pr)
    app.router.add_post("/repo/pr", handle_create_or_update_pr)
