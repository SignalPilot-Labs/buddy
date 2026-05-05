"""Regression test: PR description must include run_state.md in a collapsible details block.

Bug: PR descriptions only contained round summaries, missing the full run state
(goal, eval history, rules) that gives reviewers context on what the agent was doing.

Fix: _run_teardown reads /tmp/run_state.md from the sandbox and appends it inside
a <details> block so it's collapsed by default but accessible.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lifecycle.teardown import _run_teardown
from utils.models import RunContext, RoundsMetadata, RoundEntry


def _make_run() -> RunContext:
    return RunContext(
        run_id="run-pr-state-test",
        agent_role="default",
        branch_name="fix/branch",
        base_branch="main",
        duration_minutes=30.0,
        github_repo="owner/repo",
    )


def _make_metadata(rounds: list[RoundEntry], pr_title: str) -> AsyncMock:
    meta = RoundsMetadata(pr_title=pr_title, rounds=rounds)
    store = AsyncMock()
    store.load = AsyncMock(return_value=meta)
    return store


class TestTeardownPRRunState:
    """PR description includes run_state.md content."""

    @pytest.mark.asyncio
    async def test_run_state_included_in_pr_description(self) -> None:
        """When run_state.md exists, it appears in a <details> block in the PR body."""
        run = _make_run()
        sandbox = AsyncMock()
        run_state_content = "## Goal\n\nFix the flaky test.\n\n## Eval History\n\n- Round 1: 3/5 passing"
        sandbox.file_system.read = AsyncMock(return_value=run_state_content)
        sandbox.repo.teardown = AsyncMock(return_value=AsyncMock(
            auto_committed=False, commits_ahead=1, pushed=True,
            push_error=None, pr_url="https://github.com/o/r/pull/1",
            pr_error=None, diff_stats=[],
        ))

        metadata = _make_metadata(
            [RoundEntry(n=1, summary="Fixed test", ended_at="2025-01-01T00:00:00Z")],
            pr_title="Fix flaky test",
        )

        with patch("lifecycle.teardown.log_audit", new_callable=AsyncMock):
            await _run_teardown(sandbox=sandbox, run=run, metadata_store=metadata)

        call_args = sandbox.repo.teardown.call_args
        pr_description: str = call_args.kwargs["pr_description"]

        assert "<details>" in pr_description
        assert "<summary>Run State</summary>" in pr_description
        assert "## Goal" in pr_description
        assert "Fix the flaky test." in pr_description
        assert "</details>" in pr_description

    @pytest.mark.asyncio
    async def test_run_state_absent_when_file_missing(self) -> None:
        """When run_state.md doesn't exist, no <details> block is added."""
        run = _make_run()
        sandbox = AsyncMock()
        sandbox.file_system.read = AsyncMock(return_value=None)
        sandbox.repo.teardown = AsyncMock(return_value=AsyncMock(
            auto_committed=False, commits_ahead=1, pushed=True,
            push_error=None, pr_url="https://github.com/o/r/pull/2",
            pr_error=None, diff_stats=[],
        ))

        metadata = _make_metadata([], pr_title="Empty run")

        with patch("lifecycle.teardown.log_audit", new_callable=AsyncMock):
            await _run_teardown(sandbox=sandbox, run=run, metadata_store=metadata)

        call_args = sandbox.repo.teardown.call_args
        pr_description: str = call_args.kwargs["pr_description"]

        assert "<details>" not in pr_description
        assert "Run State" not in pr_description

    @pytest.mark.asyncio
    async def test_run_state_read_uses_correct_path(self) -> None:
        """run_state.md is read from /tmp/run_state.md."""
        run = _make_run()
        sandbox = AsyncMock()
        sandbox.file_system.read = AsyncMock(return_value=None)
        sandbox.repo.teardown = AsyncMock(return_value=AsyncMock(
            auto_committed=False, commits_ahead=0, pushed=False,
            push_error=None, pr_url=None, pr_error=None, diff_stats=[],
        ))

        metadata = _make_metadata([], pr_title="No changes")

        with patch("lifecycle.teardown.log_audit", new_callable=AsyncMock):
            await _run_teardown(sandbox=sandbox, run=run, metadata_store=metadata)

        sandbox.file_system.read.assert_called_once_with("/tmp/run_state.md")
