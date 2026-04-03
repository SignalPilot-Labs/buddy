"""Run teardown: push branch, create PR, capture diff, finish DB record."""

import logging

from utils import db
from utils.git import GitWorkspace
from utils.models import RunContext

log = logging.getLogger("core.teardown")


class RunTeardown:
    """Finalizes a completed run: push, PR, diff stats, DB update.

    Public API:
        finalize(ctx, status) — push branch, create PR, finish DB record
    """

    def __init__(self, git: GitWorkspace):
        self._git = git

    async def finalize(self, ctx: RunContext, status: str) -> str | None:
        """Push, create PR, capture diff, finish DB. Returns PR URL or None."""
        pr_url = None

        if status != "killed":
            pr_url = await self._push_and_pr(ctx)

        diff_stats = self._capture_diff(ctx)

        await db.finish_run(
            ctx.run_id, status, pr_url,
            ctx.total_cost, ctx.total_input_tokens, ctx.total_output_tokens,
            None, None, diff_stats,
        )
        log.info("Run complete: status=%s cost=$%.2f", status, ctx.total_cost)
        return pr_url

    async def _push_and_pr(self, ctx: RunContext) -> str | None:
        """Push branch and create PR. Returns PR URL or None."""
        try:
            if self._git.get_current_branch() != ctx.branch_name:
                log.warning("Not on expected branch %s, skipping push/PR", ctx.branch_name)
                return None

            # Save any uncommitted work before pushing
            if self._git.has_changes():
                log.info("Committing uncommitted changes before push")
                try:
                    self._git.run_git(["add", "-u"])
                    self._git.run_git(["commit", "-m", "Auto-commit: save uncommitted work at session end"])
                    await db.log_audit(ctx.run_id, "auto_commit", {"reason": "uncommitted changes at teardown"})
                except RuntimeError as e:
                    log.warning("Auto-commit failed: %s", e)

            self._git.push_branch(ctx.branch_name)
            pr_url = self._git.create_pr(ctx.branch_name, ctx.run_id, ctx.base_branch)
            log.info("PR created: %s", pr_url)
            await db.log_audit(ctx.run_id, "pr_created", {"url": pr_url})
            return pr_url
        except Exception as e:
            log.error("PR failed: %s", e)
            await db.log_audit(ctx.run_id, "pr_failed", {"error": str(e)})
        return None

    def _capture_diff(self, ctx: RunContext) -> list[dict] | None:
        """Capture diff stats. Returns list or None on failure."""
        try:
            return self._git.get_branch_diff(ctx.branch_name, ctx.base_branch)
        except (RuntimeError, OSError, ValueError) as e:
            log.warning("Failed to capture diff stats: %s", e)
            return None
