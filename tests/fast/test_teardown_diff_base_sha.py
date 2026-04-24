"""Regression test for handle_teardown using branch name instead of base_sha in diff.

Bug: The success path (after push+PR) called _branch_diff(working_branch, base, timeout)
where `base` is the branch name string from the request body. The other two paths
(no commits ahead, push error) correctly used state.base_sha. This meant the final
diff after a successful push used the current tip of the base branch rather than the
SHA captured at bootstrap, so merged-in upstream commits could appear as deletions.

Fix: Replace `base` with `state.base_sha` on line 155.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


BASE_BRANCH = "main"
BASE_SHA = "abc1234deadbeef"
WORKING_BRANCH = "autofyn/2026-04-24-fix123"
TIMEOUT = 60


def _make_state() -> MagicMock:
    """Build a RepoState-like mock with base_sha and working_branch."""
    state = MagicMock()
    state.base_sha = BASE_SHA
    state.working_branch = WORKING_BRANCH
    return state


def _make_request(state: MagicMock) -> MagicMock:
    """Build an aiohttp Request mock for handle_teardown."""
    request = MagicMock()
    request.json = AsyncMock(return_value={
        "pr_title": "Test PR",
        "pr_description": "desc",
        "base": BASE_BRANCH,
        "timeout": TIMEOUT,
    })
    # _state(request) reads from request.app
    request.app = {
        "repo_state": state,
    }
    return request


class TestTeardownDiffBaseSha:
    """handle_teardown must pass state.base_sha to _branch_diff in all paths."""

    @pytest.mark.asyncio
    async def test_success_path_uses_base_sha(self) -> None:
        """After push+PR, _branch_diff must receive state.base_sha, not the branch name."""
        state = _make_state()
        request = _make_request(state)
        fake_diff: list[dict] = [{"file": "foo.py", "additions": 1, "deletions": 0}]

        with (
            patch("handlers.repo._state", return_value=state),
            patch("handlers.repo._validate_branch"),
            patch("handlers.repo._require_on_working_branch", new_callable=AsyncMock),
            patch("handlers.repo._has_changes", new_callable=AsyncMock, return_value=False),
            patch("handlers.repo._commits_ahead", new_callable=AsyncMock, return_value=3),
            patch("handlers.repo._push", new_callable=AsyncMock, return_value=None),
            patch(
                "handlers.repo._create_or_update_pr",
                new_callable=AsyncMock,
                return_value=("https://github.com/owner/repo/pull/1", None),
            ),
            patch(
                "handlers.repo._branch_diff",
                new_callable=AsyncMock,
                return_value=fake_diff,
            ) as mock_diff,
        ):
            from handlers.repo import handle_teardown
            await handle_teardown(request)

        mock_diff.assert_called_once()
        _, call_args, _ = mock_diff.mock_calls[0]
        assert call_args[1] == BASE_SHA, (
            f"Expected _branch_diff called with base_sha={BASE_SHA!r}, "
            f"got {call_args[1]!r}"
        )
        assert call_args[1] != BASE_BRANCH, (
            "Must not pass the branch name string to _branch_diff"
        )

    @pytest.mark.asyncio
    async def test_no_commits_path_uses_base_sha(self) -> None:
        """When no commits ahead, _branch_diff must also receive state.base_sha."""
        state = _make_state()
        request = _make_request(state)

        with (
            patch("handlers.repo._state", return_value=state),
            patch("handlers.repo._validate_branch"),
            patch("handlers.repo._require_on_working_branch", new_callable=AsyncMock),
            patch("handlers.repo._has_changes", new_callable=AsyncMock, return_value=False),
            patch("handlers.repo._commits_ahead", new_callable=AsyncMock, return_value=0),
            patch(
                "handlers.repo._branch_diff",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_diff,
        ):
            from handlers.repo import handle_teardown
            await handle_teardown(request)

        mock_diff.assert_called_once()
        _, call_args, _ = mock_diff.mock_calls[0]
        assert call_args[1] == BASE_SHA

    @pytest.mark.asyncio
    async def test_push_error_path_uses_base_sha(self) -> None:
        """When push fails, _branch_diff must also receive state.base_sha."""
        state = _make_state()
        request = _make_request(state)

        with (
            patch("handlers.repo._state", return_value=state),
            patch("handlers.repo._validate_branch"),
            patch("handlers.repo._require_on_working_branch", new_callable=AsyncMock),
            patch("handlers.repo._has_changes", new_callable=AsyncMock, return_value=False),
            patch("handlers.repo._commits_ahead", new_callable=AsyncMock, return_value=2),
            patch("handlers.repo._push", new_callable=AsyncMock, return_value="push failed"),
            patch(
                "handlers.repo._branch_diff",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_diff,
        ):
            from handlers.repo import handle_teardown
            await handle_teardown(request)

        mock_diff.assert_called_once()
        _, call_args, _ = mock_diff.mock_calls[0]
        assert call_args[1] == BASE_SHA
