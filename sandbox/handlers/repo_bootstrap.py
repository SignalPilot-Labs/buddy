"""Bootstrap handler for /repo/bootstrap.

Orchestrates the full setup phase: clone, base-branch verification,
working-branch setup. Constructs RepoState and stores it on the app.
"""

import logging

from aiohttp import web

from constants import (
    CLONE_TMP_DIR,
    GIT_CLONE_DEPTH,
    REPO_WORK_DIR,
)
from handlers.repo_git import (
    _fail,
    _git,
    _install_git_credentials,
    _run,
    _validate_branch,
)
from models import RepoState

log = logging.getLogger("sandbox.endpoints.repo")


def _parse_bootstrap_request(
    body: dict,
) -> tuple[str, str, str, str, int]:
    """Extract and validate fields from the bootstrap request body.

    Returns (repo, token, base_branch, working_branch, timeout).
    """
    repo: str = body["repo"]
    token: str = body["token"]
    base_branch: str = body["base_branch"]
    working_branch: str = body["working_branch"]
    timeout: int = body["timeout"]

    if "/" not in repo:
        raise web.HTTPBadRequest(reason="repo must be owner/name")
    _validate_branch(base_branch)
    _validate_branch(working_branch)

    return repo, token, base_branch, working_branch, timeout


async def _clone_repo(repo: str, timeout: int) -> None:
    """Clone repo into a temp dir, then rsync into REPO_WORK_DIR.

    Host bind mounts may already exist under REPO_WORK_DIR, making
    it non-empty. rm -rf can't remove mount points, and git clone
    refuses non-empty dirs. Cloning to CLONE_TMP_DIR then rsync
    merges into existing dirs without touching mount points.
    """
    await _run(["rm", "-rf", CLONE_TMP_DIR], "/", timeout)
    await _run(["mkdir", "-p", CLONE_TMP_DIR], "/", timeout)
    await _run(["rm", "-rf", REPO_WORK_DIR], "/", timeout)
    await _run(["mkdir", "-p", REPO_WORK_DIR], "/", timeout)

    remote_url = f"https://github.com/{repo}.git"
    _fail(
        await _git(
            ["clone", "--depth", str(GIT_CLONE_DEPTH), "--no-single-branch", remote_url, "."],
            timeout,
            cwd=CLONE_TMP_DIR,
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
    rsync_cmd += [f"{CLONE_TMP_DIR}/", f"{REPO_WORK_DIR}/"]
    _fail(await _run(rsync_cmd, "/", timeout), "rsync clone into repo dir")
    await _run(["rm", "-rf", CLONE_TMP_DIR], "/", timeout)


async def _setup_base_branch(base_branch: str, timeout: int) -> str:
    """Verify base exists on origin, fetch, checkout, and return base_sha."""
    _fail(
        await _git(
            ["ls-remote", "--exit-code", "--heads", "origin", base_branch],
            timeout,
            cwd=REPO_WORK_DIR,
        ),
        f"base branch '{base_branch}' not found on origin",
    )

    _fail(
        await _git(["fetch", "origin", base_branch], timeout, cwd=REPO_WORK_DIR),
        "git fetch",
    )
    _fail(
        await _git(
            ["checkout", "-B", base_branch, f"origin/{base_branch}"],
            timeout,
            cwd=REPO_WORK_DIR,
        ),
        "git checkout base",
    )

    # Freeze the base SHA now. Every subsequent diff uses this SHA —
    # independent of base moving on after bootstrap.
    sha_result = await _git(
        ["rev-parse", f"origin/{base_branch}"], timeout, cwd=REPO_WORK_DIR,
    )
    _fail(sha_result, f"git rev-parse origin/{base_branch}")
    base_sha = sha_result.stdout.strip()
    if not base_sha:
        raise web.HTTPInternalServerError(
            reason=f"git rev-parse origin/{base_branch} returned empty SHA",
        )
    return base_sha


async def _setup_working_branch(working_branch: str, timeout: int) -> None:
    """Check out or create the working branch.

    If working_branch exists on origin, fetch and check it out (resume path).
    Otherwise create it from the current HEAD (fresh run path).
    """
    ls_result = await _git(
        ["ls-remote", "--exit-code", "--heads", "origin", working_branch],
        timeout,
        cwd=REPO_WORK_DIR,
    )
    if ls_result.exit_code == 0:
        _fail(
            await _git(
                ["fetch", "origin", working_branch], timeout, cwd=REPO_WORK_DIR,
            ),
            "git fetch working branch",
        )
        _fail(
            await _git(
                ["checkout", "-b", working_branch, f"origin/{working_branch}"],
                timeout,
                cwd=REPO_WORK_DIR,
            ),
            "git checkout existing branch",
        )
    else:
        _fail(
            await _git(["checkout", "-b", working_branch], timeout, cwd=REPO_WORK_DIR),
            "git checkout -b",
        )


async def handle_bootstrap(request: web.Request) -> web.Response:
    """Clone the repo, verify the base branch exists, create the working
    branch. One round-trip for the entire setup phase.

    This is the only handler that constructs `RepoState`. All other
    endpoints require it to exist and fail fast otherwise.
    """
    body = await request.json()
    repo, token, base_branch, working_branch, timeout = _parse_bootstrap_request(body)

    await _install_git_credentials(token, timeout)
    await _clone_repo(repo, timeout)
    base_sha = await _setup_base_branch(base_branch, timeout)
    await _setup_working_branch(working_branch, timeout)

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
