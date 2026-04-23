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

from aiohttp import web

from constants import (
    AUTO_COMMIT_MESSAGE,
    CMD_TIMEOUT,
    REPO_WORK_DIR,
    STDERR_SHORT_LIMIT,
)
from handlers.repo_bootstrap import handle_bootstrap
from handlers.repo_git import (
    _branch_diff,
    _commit,
    _commits_ahead,
    _create_or_update_pr,
    _git,
    _has_changes,
    _push,
    _require_on_working_branch,
    _scrub_secrets,
    _state,
    _validate_branch,
    _worktree_diff,
)


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


def _build_teardown_response(
    auto_committed: bool,
    commits_ahead: int,
    pushed: bool,
    push_error: str | None,
    pr_url: str | None,
    pr_error: str | None,
    diff_stats: list[dict],
) -> dict:
    """Construct the teardown response dict from collected data."""
    return {
        "auto_committed": auto_committed,
        "commits_ahead": commits_ahead,
        "pushed": pushed,
        "push_error": push_error,
        "pr_url": pr_url,
        "pr_error": pr_error,
        "diff_stats": diff_stats,
    }


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
        auto_committed = await _commit(AUTO_COMMIT_MESSAGE, timeout)

    ahead = await _commits_ahead(base, timeout)
    if ahead == 0:
        diff = await _branch_diff(state.working_branch, state.base_sha, timeout)
        return web.json_response(
            _build_teardown_response(auto_committed, 0, False, None, None, None, diff)
        )

    push_error = await _push(state.working_branch, timeout)
    if push_error is not None:
        diff = await _branch_diff(state.working_branch, state.base_sha, timeout)
        return web.json_response(
            _build_teardown_response(
                auto_committed, ahead, False, push_error, None, None, diff,
            )
        )

    pr_url, pr_error = await _create_or_update_pr(
        state, pr_title, pr_description, base, timeout,
    )
    diff = await _branch_diff(state.working_branch, base, timeout)
    return web.json_response(
        _build_teardown_response(auto_committed, ahead, True, None, pr_url, pr_error, diff)
    )


# ── Handler: /repo/diff ───────────────────────────────────────────────


async def handle_diff(request: web.Request) -> web.Response:
    """Return the full unified diff of the working tree against base.

    One-arg `git diff <sha>` compares base_sha to the working tree, so
    uncommitted edits from an in-progress round are included. This is
    what the dashboard's live Changes panel shows; teardown stats use
    the committed ref-to-ref form separately.
    """
    state = _state(request)
    if not state.working_branch or not state.base_branch:
        return web.json_response({"error": "No active branch"}, status=409)

    result = await _git(["diff", state.base_sha], CMD_TIMEOUT, cwd=REPO_WORK_DIR)
    if result.exit_code != 0:
        detail = _scrub_secrets(result.stderr)[:STDERR_SHORT_LIMIT]
        return web.json_response(
            {"error": "git diff failed", "detail": detail}, status=500,
        )
    return web.json_response({"diff": result.stdout})


async def handle_diff_stats(request: web.Request) -> web.Response:
    """Return per-file diff stats without transferring the full diff body.

    Used by the dashboard Changes panel on every poll. Worktree form so
    mid-round uncommitted edits surface in the stats before `/repo/save`
    commits them — otherwise the panel badge is stuck on 'session' and
    files aren't clickable until the first commit of the round lands.
    """
    state = _state(request)
    if not state.working_branch or not state.base_branch:
        return web.json_response({"error": "No active branch"}, status=409)
    files = await _worktree_diff(state.base_sha, CMD_TIMEOUT)
    return web.json_response({"files": files})


# ── Registration ─────────────────────────────────────────────────────


def register(app: web.Application) -> None:
    """Attach /repo/* routes."""
    app.router.add_post("/repo/bootstrap", handle_bootstrap)
    app.router.add_post("/repo/save", handle_save)
    app.router.add_post("/repo/teardown", handle_teardown)
    app.router.add_post("/repo/diff", handle_diff)
    app.router.add_post("/repo/diff/stats", handle_diff_stats)
