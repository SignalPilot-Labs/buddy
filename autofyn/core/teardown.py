"""Run teardown: push branch, create PR, capture diff, finish DB record."""

import logging

from utils import db
from utils.constants import WORK_DIR
from utils.models import RunContext
from sandbox_manager.repo_ops import RepoOps

log = logging.getLogger("core.teardown")


class RunTeardown:
    """Finalizes a completed run: push, PR, diff stats, DB update.

    Public API:
        finalize(run_context, status, exec_timeout) — push branch, create PR, finish DB record
    """

    def __init__(self, repo_ops: RepoOps) -> None:
        self._repo_ops = repo_ops

    async def finalize(self, run_context: RunContext, status: str, exec_timeout: int) -> str | None:
        """Push, create PR, capture diff, finish DB. Returns PR URL or None."""
        pr_url = None

        if status != "killed":
            pr_url = await self._push_and_pr(run_context, exec_timeout)

        diff_stats = await self._capture_diff(run_context, exec_timeout)

        await db.finish_run(
            run_context.run_id, status, pr_url,
            run_context.total_cost, run_context.total_input_tokens, run_context.total_output_tokens,
            None, None, diff_stats,
        )
        log.info("Run complete: status=%s cost=$%.2f", status, run_context.total_cost)
        return pr_url

    async def _push_and_pr(self, run_context: RunContext, exec_timeout: int) -> str | None:
        """Push branch and create PR. Returns PR URL or None."""
        try:
            current = await self._repo_ops.run_git(["branch", "--show-current"], exec_timeout, WORK_DIR)
            if current != run_context.branch_name:
                log.warning(
                    "Not on expected branch %s (on %s), skipping push/PR",
                    run_context.branch_name, current,
                )
                return None

            # Save any uncommitted work before pushing
            if await self._repo_ops.has_changes(exec_timeout):
                log.info("Committing uncommitted changes before push")
                try:
                    await self._repo_ops.run_git(["add", "."], exec_timeout, WORK_DIR)
                    await self._repo_ops.run_git(
                        ["commit", "-m", "Auto-commit: save uncommitted work at session end"],
                        exec_timeout,
                        WORK_DIR,
                    )
                    await db.log_audit(run_context.run_id, "auto_commit", {
                        "reason": "uncommitted changes at teardown",
                    })
                except RuntimeError as e:
                    log.warning("Auto-commit failed: %s", e)

            await self._repo_ops.push_branch(run_context.branch_name, exec_timeout)
            pr_url = await self._repo_ops.create_pr(
                run_context.branch_name, run_context.run_id, run_context.base_branch, exec_timeout,
            )
            log.info("PR created: %s", pr_url)
            await db.log_audit(run_context.run_id, "pr_created", {"url": pr_url})
            return pr_url
        except Exception as e:
            log.error("PR failed: %s", e)
            await db.log_audit(run_context.run_id, "pr_failed", {"error": str(e)})
        return None

    async def _capture_diff(self, run_context: RunContext, exec_timeout: int) -> list[dict] | None:
        """Capture diff stats. Returns list or None on failure."""
        try:
            return await self._repo_ops.get_branch_diff(
                run_context.branch_name, run_context.base_branch, exec_timeout,
            )
        except (RuntimeError, ValueError) as e:
            log.warning("Failed to capture diff stats: %s", e)
            return None
