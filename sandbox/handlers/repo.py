"""Repo HTTP handlers for the sandbox.

Three endpoints map to the three fixed phases of an agent run. Each
endpoint bundles every git/gh operation that phase needs into a single
round-trip, so the agent container never has to sequence primitives.

Endpoints:
    POST /repo/bootstrap   clone + verify base + create working branch
    POST /repo/save        commit + push per-round changes (no-op if clean)
    POST /repo/teardown    commit leftovers + push + PR + diff stats
    POST /repo/diff        full unified diff of working branch against base

Auth is stored in a module-level variable in repo_env; each authenticated
git/gh subprocess receives GIT_TOKEN/GH_TOKEN via its own env= dict.
Nothing is written to os.environ. The credential helper still reads
$GIT_TOKEN, but $GIT_TOKEN is set only in the env of the specific
process that needs it.

Security rules (enforced here because they protect against orchestrator
bugs — not malicious subagents, which gVisor + SDK SecurityGate handle):
    1. Working branch is set by bootstrap and never changes. `save` and
       `teardown` refuse if HEAD doesn't match it.
    2. Push is always `push -u origin <working_branch>` — no refspec,
       no other target.
    3. PR create/update always uses the working branch as head.
"""

import logging

from aiohttp import web

from constants import (
    CMD_TIMEOUT,
    REPO_BRANCH_NAME_MAX_LEN,
    REPO_BRANCH_NAME_PATTERN,
    REPO_WORK_DIR,
)
from handlers import repo_env
from handlers.repo_phases import (
    _branch_diff,
    _commits_ahead,
    _create_or_update_pr,
    _fail,
    _git,
    _run,
)
from models import RepoState

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


# ── Credential setup ─────────────────────────────────────────────────


async def _store_git_token(token: str) -> None:
    """Store the token in the module-level holder.

    With GIT_CONFIG_GLOBAL=/dev/null set by build_git_env (F5), any global
    git config write would go to /dev/null. The credential helper is now
    injected per-invocation via PER_CALL_GIT_CONFIG_FLAGS in _git, so no
    git config --global write is needed here.
    """
    repo_env.set_git_token(token)


# ── Private git op helpers (called by handlers below) ────────────────


async def _require_on_working_branch(state: RepoState, timeout: int) -> None:
    """Refuse if HEAD isn't on the expected working branch."""
    current = await _git(["branch", "--show-current"], timeout, with_token=False)
    head = current.stdout.strip()
    if head != state.working_branch:
        raise web.HTTPConflict(
            reason=f"HEAD is on '{head}', not working branch '{state.working_branch}'",
        )


async def _has_changes(timeout: int) -> bool:
    """True if the working tree has uncommitted or staged changes."""
    result = await _git(["status", "--porcelain"], timeout, with_token=False)
    _fail(result, "git status")
    return bool(result.stdout.strip())


async def _commit(message: str, timeout: int) -> bool:
    """Stage everything and commit. Returns True on commit, False if clean."""
    _fail(await _git(["add", "."], timeout, with_token=False), "git add")
    result = await _git(["commit", "-m", message], timeout, with_token=False)
    if result.exit_code != 0 and "nothing to commit" in (result.stdout + result.stderr):
        return False
    _fail(result, "git commit")
    return True


async def _push(working_branch: str, timeout: int) -> str | None:
    """Push working branch to origin. Returns error string on failure, None on success."""
    result = await _git(["push", "-u", "origin", working_branch], timeout, with_token=True)
    if result.exit_code != 0:
        err = result.stderr.strip()[:500]
        log.warning("push failed: %s", err)
        return err
    return None


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

    await _store_git_token(token)

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
            with_token=True,
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
            with_token=True,
        ),
        f"base branch '{base_branch}' not found on origin",
    )

    _fail(await _git(["fetch", "origin", base_branch], timeout, with_token=True), "git fetch")
    _fail(
        await _git(["checkout", "-B", base_branch, f"origin/{base_branch}"], timeout, with_token=False),
        "git checkout base",
    )

    # Freeze the base SHA now. Every subsequent diff (teardown stats,
    # live /repo/diff/stats) uses this SHA — independent of base moving on.
    sha_result = await _git(["rev-parse", f"origin/{base_branch}"], timeout, with_token=False)
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
        with_token=True,
    )
    if ls_result.exit_code == 0:
        _fail(
            await _git(["fetch", "origin", working_branch], timeout, with_token=True),
            "git fetch working branch",
        )
        _fail(
            await _git(
                ["checkout", "-b", working_branch, f"origin/{working_branch}"],
                timeout, with_token=False,
            ),
            "git checkout existing branch",
        )
    else:
        _fail(
            await _git(["checkout", "-b", working_branch], timeout, with_token=False),
            "git checkout -b",
        )

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
    diff = await _branch_diff(state.working_branch, state.base_sha, timeout)
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
        ["diff", state.base_sha, state.working_branch], CMD_TIMEOUT, with_token=False,
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
