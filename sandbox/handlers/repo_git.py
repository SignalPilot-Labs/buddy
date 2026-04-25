"""Git/gh operation primitives for sandbox repo handlers.

All subprocess execution, git/gh command wrappers, credential management,
and composable git operations live here. Handler files import from this
module — this module never imports from handler files.
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
    RETRY_BASE_DELAY_SEC,
    RETRY_MAX_ATTEMPTS,
    RETRY_TRANSIENT_PATTERNS,
    SECRET_REDACT_MASK,
    STDERR_BRIEF_LIMIT,
    STDERR_DISPLAY_LIMIT,
    STDERR_SHORT_LIMIT,
)
from handlers.repo_parse import _parse_name_status, _parse_numstat
from models import CmdResult, RepoState

log = logging.getLogger("sandbox.endpoints.repo")

_SECRET_ENV_KEYS: tuple[str, ...] = ("GIT_TOKEN", "GH_TOKEN")


def _scrub_secrets(text: str) -> str:
    """Replace any in-process git/gh token value with SECRET_REDACT_MASK.

    The sandbox installs `GIT_TOKEN` / `GH_TOKEN` in its own process env at
    bootstrap (see `_install_git_credentials`). Every git/gh subprocess
    inherits them, and any subprocess error that surfaces their values in
    stderr/stdout would leak the PAT to logs, exception bodies, or HTTP
    responses. This helper masks the raw value before any such crossing.

    Reads `os.environ` at call time — not a cached snapshot — because
    `_install_git_credentials` mutates env mid-process and tests reset env
    between cases.
    """
    scrubbed = text
    for key in _SECRET_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            scrubbed = scrubbed.replace(value, SECRET_REDACT_MASK)
    return scrubbed


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
            exit_code=proc.returncode if proc.returncode is not None else -1,
        )
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
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
            log.warning(
                "%s: transient error, retry %d/%d in %.0fs",
                cmd[0], attempt + 1, RETRY_MAX_ATTEMPTS, delay,
            )
            await asyncio.sleep(delay)
    return result


async def _git(args: list[str], timeout: int, cwd: str) -> CmdResult:
    """Run `git <args>` with retry on transient network errors."""
    return await _with_retry(["git"] + args, cwd, timeout)


async def _gh(args: list[str], timeout: int, cwd: str) -> CmdResult:
    """Run `gh <args>` with retry on transient network errors."""
    return await _with_retry(["gh"] + args, cwd, timeout)


def _fail(result: CmdResult, label: str) -> None:
    """Raise HTTP 500 with the git/gh error in the JSON body on failure.

    Stderr goes into the body (not the HTTP reason header) because
    aiohttp rejects reason values containing `\\r` or `\\n`, and git
    stderr routinely contains newlines.
    """
    if result.exit_code != 0:
        stderr = _scrub_secrets(result.stderr.strip())[:STDERR_DISPLAY_LIMIT]
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
        timeout,
        cwd="/",
    )
    _fail(cfg, "git config credential.helper")


# ── Private git op helpers ────────────────────────────────────────────


async def _require_on_working_branch(state: RepoState, timeout: int) -> None:
    """Refuse if HEAD isn't on the expected working branch."""
    current = await _git(["branch", "--show-current"], timeout, cwd=REPO_WORK_DIR)
    head = current.stdout.strip()
    if head != state.working_branch:
        raise web.HTTPConflict(
            reason=f"HEAD is on '{head}', not working branch '{state.working_branch}'",
        )


async def _has_changes(timeout: int) -> bool:
    """True if the working tree has uncommitted or staged changes."""
    result = await _git(["status", "--porcelain"], timeout, cwd=REPO_WORK_DIR)
    _fail(result, "git status")
    return bool(result.stdout.strip())


async def _commit(message: str, timeout: int) -> bool:
    """Stage everything and commit. Returns True on commit, False if clean."""
    _fail(await _git(["add", "."], timeout, cwd=REPO_WORK_DIR), "git add")
    result = await _git(["commit", "-m", message], timeout, cwd=REPO_WORK_DIR)
    if result.exit_code != 0 and "nothing to commit" in (result.stdout + result.stderr):
        return False
    _fail(result, "git commit")
    return True


async def _push(working_branch: str, timeout: int) -> str | None:
    """Push working branch to origin. Returns error string on failure, None on success."""
    result = await _git(
        ["push", "-u", "origin", working_branch], timeout, cwd=REPO_WORK_DIR,
    )
    if result.exit_code != 0:
        err = _scrub_secrets(result.stderr.strip())[:STDERR_SHORT_LIMIT]
        log.warning("push failed: %s", err)
        return err
    return None


async def _commits_ahead(base: str, timeout: int) -> int:
    """Count commits between origin/base and HEAD."""
    _fail(
        await _git(["fetch", "origin", base, "--depth", "1"], timeout, cwd=REPO_WORK_DIR),
        "git fetch base",
    )
    result = await _git(
        ["rev-list", "--count", f"origin/{base}..HEAD"], timeout, cwd=REPO_WORK_DIR,
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
    unaffected by shallow fetches or force-updated bases. Ref-to-ref
    form excludes uncommitted working-tree edits — which is correct
    for teardown (the PR carries only committed changes) but wrong for
    live polling during a round; see `_worktree_diff`.
    """
    numstat = await _git(
        ["diff", "--numstat", base_sha, working_branch], timeout, cwd=REPO_WORK_DIR,
    )
    if numstat.exit_code != 0 or not numstat.stdout.strip():
        return []
    name_status = await _git(
        ["diff", "--name-status", base_sha, working_branch], timeout, cwd=REPO_WORK_DIR,
    )
    if name_status.exit_code != 0:
        return []
    return _parse_numstat(numstat.stdout, _parse_name_status(name_status.stdout))


async def _worktree_diff(base_sha: str, timeout: int) -> list[dict]:
    """File-level diff stats between the working tree and the base-point SHA.

    One-arg `git diff <sha>` compares the working tree (including staged
    and unstaged edits) against the given commit, so uncommitted changes
    from an in-progress round are surfaced. Used by the dashboard's live
    Changes panel so the badge and file tree populate mid-round, not
    only after `/repo/save` commits.
    """
    numstat = await _git(
        ["diff", "--numstat", base_sha], timeout, cwd=REPO_WORK_DIR,
    )
    if numstat.exit_code != 0 or not numstat.stdout.strip():
        return []
    name_status = await _git(
        ["diff", "--name-status", base_sha], timeout, cwd=REPO_WORK_DIR,
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
        cwd=REPO_WORK_DIR,
    )
    existing = find.stdout.strip() if find.exit_code == 0 else ""

    if existing:
        edit = await _gh(
            ["pr", "edit", existing, "--title", title, "--body", description],
            timeout,
            cwd=REPO_WORK_DIR,
        )
        if edit.exit_code != 0:
            err = _scrub_secrets(edit.stderr.strip())[:STDERR_BRIEF_LIMIT]
            return existing, f"gh pr edit failed: {err}"
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
        cwd=REPO_WORK_DIR,
    )
    if create.exit_code != 0:
        err = _scrub_secrets(create.stderr.strip())[:STDERR_BRIEF_LIMIT]
        return None, f"gh pr create failed: {err}"
    return create.stdout.strip(), None
