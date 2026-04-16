"""Subprocess helpers and phase helpers for the sandbox repo handlers.

Extracted from repo.py to keep that file under the 400-line limit.
Contains:
  - _run / _with_retry   core subprocess execution
  - _git / _gh           git/gh wrappers with explicit token injection
  - _fail                error raiser for non-zero exit codes
  - _commits_ahead       fetch + rev-list helper used in teardown
  - _branch_diff         file-level diff stats between working branch and base
  - _create_or_update_pr PR create/update via `gh`

Auth note: _run always uses build_git_env(with_token=False). _git requires
with_token as a keyword-only argument (forgetting it is a pyright error).
_gh hard-codes with_token=True — every gh call in this file needs auth.
"""

import asyncio
import json
import logging
import subprocess

from aiohttp import web

from constants import (
    PER_CALL_GIT_CONFIG_FLAGS,
    REPO_WORK_DIR,
    RETRY_BASE_DELAY_SEC,
    RETRY_MAX_ATTEMPTS,
    RETRY_TRANSIENT_PATTERNS,
)
from handlers.repo_env import build_git_env
from handlers.repo_parse import _parse_name_status, _parse_numstat
from models import CmdResult, RepoState

log = logging.getLogger("sandbox.endpoints.repo")


# ── Core subprocess helpers ──────────────────────────────────────────


async def _run(args: list[str], cwd: str, timeout: int) -> CmdResult:
    """Run a subprocess with the no-token safe env (secrets stripped)."""
    proc: asyncio.subprocess.Process | None = None
    env = build_git_env(with_token=False)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env,
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


async def _with_retry(cmd: list[str], cwd: str, timeout: int, env: dict[str, str]) -> CmdResult:
    """Run a command with exponential backoff on transient failures."""
    result = CmdResult(stdout="", stderr="", exit_code=-1)
    for attempt in range(RETRY_MAX_ATTEMPTS):
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            result = CmdResult(
                stdout=(stdout or b"").decode(),
                stderr=(stderr or b"").decode(),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            return CmdResult(stdout="", stderr="timed out", exit_code=-1)
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


async def _git(args: list[str], timeout: int, cwd: str = REPO_WORK_DIR, *, with_token: bool) -> CmdResult:
    """Run `git <args>` with retry on transient network errors.

    with_token is required keyword-only: forgetting it is a pyright error,
    not a silent token leak.

    PER_CALL_GIT_CONFIG_FLAGS are prepended between `git` and the subcommand
    to ensure credential.helper, include.path, core.sshCommand, and
    protocol.ext.allow are always set to safe values for handler-owned calls.
    """
    env = build_git_env(with_token=with_token)
    cmd = ["git"] + list(PER_CALL_GIT_CONFIG_FLAGS) + args
    return await _with_retry(cmd, cwd, timeout, env)


async def _gh(args: list[str], timeout: int, cwd: str = REPO_WORK_DIR) -> CmdResult:
    """Run `gh <args>` with retry on transient network errors.

    Always uses with_token=True — every gh call needs auth via GH_TOKEN.
    """
    env = build_git_env(with_token=True)
    return await _with_retry(["gh"] + args, cwd, timeout, env)


def _fail(result: CmdResult, label: str) -> None:
    """Raise HTTP 500 with the git/gh error in the JSON body on failure.

    Stderr goes into the body (not the HTTP reason header) because
    aiohttp rejects reason values containing \\r or \\n, and git
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


# ── Phase helpers (used by handle_teardown and handle_diff) ─────────


async def _commits_ahead(base: str, timeout: int) -> int:
    """Count commits between origin/base and HEAD."""
    _fail(
        await _git(["fetch", "origin", base, "--depth", "1"], timeout, with_token=True),
        "git fetch base",
    )
    result = await _git(
        ["rev-list", "--count", f"origin/{base}..HEAD"], timeout, with_token=False,
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
    current `origin/<base>` tip) means only changes the branch
    introduced are surfaced, and no extra fetch is needed per call.
    Two-arg form (`git diff A B`) avoids the merge-base requirement
    that three-dot form has.
    """
    numstat = await _git(["diff", "--numstat", base_sha, working_branch], timeout, with_token=False)
    if numstat.exit_code != 0 or not numstat.stdout.strip():
        return []
    name_status = await _git(["diff", "--name-status", base_sha, working_branch], timeout, with_token=False)
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
