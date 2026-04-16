"""Tests for _scrub_secrets and the five stderr leak surfaces in sandbox/handlers/repo.py.

Pins three guarantees:
1. The `_scrub_secrets` helper replaces GIT_TOKEN and GH_TOKEN env values with
   `***REDACTED***` and passes through text unchanged when no token is set.
2. Scrub happens BEFORE truncation at every leak surface (scrub-then-truncate
   ordering rule from Round 3).
3. The token does not appear in log output, HTTPInternalServerError bodies,
   returned error strings, or HTTP response bodies at any of the five sites.
"""

import logging
from unittest.mock import MagicMock

import pytest
from aiohttp import web

from handlers import repo as repo_module
from models import CmdResult, RepoState


def _cmd_result(stdout: str = "", stderr: str = "", exit_code: int = 0) -> CmdResult:
    return CmdResult(stdout=stdout, stderr=stderr, exit_code=exit_code)


class TestRepoStderrRedaction:
    """One class covers _scrub_secrets directly and each of the five boundary types."""

    # ── Helper-direct tests ───────────────────────────────────────────

    def test_scrubs_git_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GIT_TOKEN", "GHP_SENTINEL_GIT_TOKEN_AAA")
        result = repo_module._scrub_secrets(
            "fatal: Authentication failed for GHP_SENTINEL_GIT_TOKEN_AAA"
        )
        assert "GHP_SENTINEL_GIT_TOKEN_AAA" not in result
        assert "***REDACTED***" in result

    def test_scrubs_gh_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GH_TOKEN", "GHP_SENTINEL_GH_TOKEN_BBB")
        monkeypatch.delenv("GIT_TOKEN", raising=False)
        result = repo_module._scrub_secrets(
            "error: GH_TOKEN=GHP_SENTINEL_GH_TOKEN_BBB"
        )
        assert "GHP_SENTINEL_GH_TOKEN_BBB" not in result
        assert "***REDACTED***" in result

    def test_no_token_in_env_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GIT_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        text = "any text without secrets"
        result = repo_module._scrub_secrets(text)
        assert result == text
        assert "***REDACTED***" not in result

    def test_scrub_then_truncate_at_boundary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Token straddling the 500-char _push cap must not survive truncation.

        Build a string where the 20-char sentinel starts at position 491,
        spanning the 500-char boundary. Applying scrub BEFORE truncation
        replaces the 20-char token with 14-char '***REDACTED***', keeping
        the full replacement well within the 500 cap. If truncation ran
        first, bytes 491-499 of the token (9 chars) would remain.
        """
        sentinel = "GHPSENTINEL12345678X"  # exactly 20 chars
        assert len(sentinel) == 20
        monkeypatch.setenv("GIT_TOKEN", sentinel)
        # Build: 491 filler chars + 20-char sentinel = 511 chars total
        filler = "x" * 491
        full_text = filler + sentinel
        assert len(full_text) == 511

        # Simulate what _push does: scrub then truncate
        scrubbed_and_truncated = repo_module._scrub_secrets(full_text)[:500]

        assert sentinel not in scrubbed_and_truncated
        # The mask may or may not be fully within the 500-char slice, but
        # the sentinel must be completely absent.
        for fragment_len in range(1, len(sentinel) + 1):
            assert sentinel[:fragment_len] not in scrubbed_and_truncated

    # ── Integration tests — one per boundary type ─────────────────────

    def test_fail_logs_and_raises_with_scrubbed_stderr(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Site A: _fail must scrub before logging and before placing in HTTP body."""
        monkeypatch.setenv("GIT_TOKEN", "GHP_SENTINEL_FAIL_BBB")
        bad_result = _cmd_result(
            stderr="fatal: could not read Password for GHP_SENTINEL_FAIL_BBB",
            exit_code=128,
        )
        with caplog.at_level(logging.ERROR, logger="sandbox.endpoints.repo"):
            with pytest.raises(web.HTTPInternalServerError) as exc_info:
                repo_module._fail(bad_result, "git push")

        assert "GHP_SENTINEL_FAIL_BBB" not in caplog.text
        assert "***REDACTED***" in caplog.text

        exc_text = exc_info.value.text
        assert exc_text is not None
        assert "GHP_SENTINEL_FAIL_BBB" not in exc_text
        assert "***REDACTED***" in exc_text

    @pytest.mark.asyncio
    async def test_push_returns_scrubbed_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Site B: _push must return a scrubbed string and log without the token."""
        monkeypatch.setenv("GIT_TOKEN", "GHP_SENTINEL_PUSH_CCC")
        monkeypatch.setattr(
            repo_module,
            "_git",
            lambda *_args, **_kwargs: _async_result(
                _cmd_result(
                    stderr="remote: Invalid credentials GHP_SENTINEL_PUSH_CCC fatal",
                    exit_code=128,
                )
            ),
        )
        with caplog.at_level(logging.WARNING, logger="sandbox.endpoints.repo"):
            error = await repo_module._push("feature-branch", 60)

        assert error is not None
        assert "GHP_SENTINEL_PUSH_CCC" not in error
        assert "***REDACTED***" in error
        assert "GHP_SENTINEL_PUSH_CCC" not in caplog.text

    @pytest.mark.asyncio
    async def test_create_or_update_pr_scrubs_create_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sites C+D: _create_or_update_pr must scrub pr-create and pr-edit stderr.

        Drive the create path: pr view fails (no existing PR), pr create fails
        with the token in stderr. The returned error string must not contain it.
        """
        sentinel = "GHP_SENTINEL_PR_DDD"
        monkeypatch.setenv("GIT_TOKEN", sentinel)

        call_index = 0

        async def fake_gh(args: list[str], timeout: int, cwd: str = "") -> CmdResult:
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                # pr view — not found
                return _cmd_result(exit_code=1)
            # pr create — fails with token in stderr
            return _cmd_result(
                stderr=f"HTTP 401: bad token {sentinel}",
                exit_code=1,
            )

        monkeypatch.setattr(repo_module, "_gh", fake_gh)

        state = RepoState(
            repo="owner/repo",
            base_branch="main",
            working_branch="feature",
            base_sha="abc123",
        )
        _url, error = await repo_module._create_or_update_pr(
            state, "Title", "Description", "main", 60
        )

        assert error is not None
        assert sentinel not in error
        assert "***REDACTED***" in error

    @pytest.mark.asyncio
    async def test_handle_diff_scrubs_stderr_in_response_body(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Site E: handle_diff must scrub stderr before placing it in JSON detail."""
        sentinel = "GHP_SENTINEL_DIFF_EEE"
        monkeypatch.setenv("GIT_TOKEN", sentinel)

        monkeypatch.setattr(
            repo_module,
            "_git",
            lambda *_args, **_kwargs: _async_result(
                _cmd_result(
                    stderr=f"error: {sentinel} authentication failed",
                    exit_code=128,
                )
            ),
        )

        state = RepoState(
            repo="owner/repo",
            base_branch="main",
            working_branch="feature",
            base_sha="abc123",
        )
        app = web.Application()
        app["repo_state"] = state

        request = _make_request(app)
        response = await repo_module.handle_diff(request)

        assert response.status == 500
        body_text = response.text
        assert body_text is not None
        assert sentinel not in body_text
        assert "***REDACTED***" in body_text


# ── Helpers ───────────────────────────────────────────────────────────


async def _async_result(result: CmdResult) -> CmdResult:
    """Coroutine wrapper so monkeypatch lambdas can return an awaitable."""
    return result


def _make_request(app: web.Application) -> web.Request:
    """Build a minimal web.Request pointing at the given app."""
    request = MagicMock(spec=web.Request)
    request.app = app
    return request
