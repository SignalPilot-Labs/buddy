"""Bootstrap and branch-init helpers for RepoOps."""

import logging
from typing import TYPE_CHECKING

from utils.constants import WORK_DIR

if TYPE_CHECKING:
    from sandbox_manager.repo_ops import RepoOps

log = logging.getLogger("sandbox_manager.repo_init")


async def bootstrap_empty_repo(ops: "RepoOps", base_branch: str, timeout: int) -> None:
    """Initialize an empty remote with main + staging branches."""
    try:
        await ops.run_git(["checkout", "--orphan", "main"], timeout, WORK_DIR)
        await ops.run_git(
            ["commit", "--allow-empty", "-m", "Initialize repository"], timeout, WORK_DIR,
        )
        await ops.run_git(["push", "-u", "origin", "main"], timeout, WORK_DIR)
        await ops.run_git(["checkout", "-b", "staging"], timeout, WORK_DIR)
        await ops.run_git(["push", "-u", "origin", "staging"], timeout, WORK_DIR)
        if base_branch not in ("main", "staging"):
            await ops.run_git(["checkout", "-b", base_branch], timeout, WORK_DIR)
            await ops.run_git(["push", "-u", "origin", base_branch], timeout, WORK_DIR)
        else:
            await ops.run_git(["checkout", base_branch], timeout, WORK_DIR)
    except RuntimeError as e:
        log.warning("Could not auto-init remote: %s", e)


async def create_missing_branch(ops: "RepoOps", base_branch: str, timeout: int) -> None:
    """Create a missing base branch from the default branch."""
    try:
        default = await get_default_branch(ops, timeout)
        await ops.run_git(["checkout", default], timeout, WORK_DIR)
        await ops.run_git(["checkout", "-b", base_branch], timeout, WORK_DIR)
        await ops.run_git(["push", "-u", "origin", base_branch], timeout, WORK_DIR)
    except RuntimeError as e:
        log.warning("Could not create branch '%s': %s", base_branch, e)


async def get_default_branch(ops: "RepoOps", timeout: int) -> str:
    """Detect the remote's default branch."""
    try:
        ref = await ops.run_git(
            ["symbolic-ref", "refs/remotes/origin/HEAD", "--short"], timeout, WORK_DIR,
        )
        return ref.replace("origin/", "")
    except RuntimeError:
        for name in ("main", "master"):
            try:
                await ops.run_git(
                    ["ls-remote", "--exit-code", "--heads", "origin", name],
                    timeout,
                    WORK_DIR,
                )
                return name
            except RuntimeError:
                continue
        return "main"
