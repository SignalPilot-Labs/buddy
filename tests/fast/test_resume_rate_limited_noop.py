"""Regression test — resume of rate-limited run with no prompt must return signal 'noop'.

Bug: line 154 in runs.py returned {"signal": "inject"} even though no inject
signal was sent (the `if prompt:` block was skipped). The misleading signal value
confused callers that inspected the response to decide what happened. The fix
changes the return value to {"signal": "noop"}.
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager


def _mock_run(status: str) -> MagicMock:
    """Create a mock Run ORM object with given status."""
    run = MagicMock()
    run.status = status
    run.github_repo = "org/repo"
    run.error_message = None
    return run


def _mock_session(run: MagicMock | None):
    """Create a mock async session context manager."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=run)
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def context():
        yield session_mock

    return context


@pytest.fixture(autouse=True)
def _patch_auth():
    """Stub out backend.auth so importing endpoints doesn't need /data/api.key."""
    fake_auth = MagicMock()
    fake_auth.verify_api_key = AsyncMock()
    sys.modules.setdefault("backend.auth", fake_auth)
    yield


def _import_resume_run():
    """Import resume_run after auth is patched."""
    from backend.endpoints.runs import resume_run

    return resume_run


def _make_body(payload: str | None = None):
    """Create a ControlSignalRequest."""
    from backend.models import ControlSignalRequest

    return ControlSignalRequest(payload=payload)


class TestResumeRateLimitedNoop:
    """Resuming a rate-limited run with no prompt returns signal 'noop', not 'inject'."""

    @pytest.mark.asyncio
    async def test_rate_limited_no_prompt_returns_noop_signal(self) -> None:
        """The response signal must be 'noop' when no inject was sent.

        This is the exact regression: old code returned {"signal": "inject"} even
        though the inject branch was skipped because prompt was empty.
        """
        resume_run = _import_resume_run()
        run = _mock_run("rate_limited")

        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch(
                "backend.endpoints.runs.send_control_signal", new_callable=AsyncMock
            ) as mock_signal,
        ):
            result = await resume_run(
                "00000000-0000-0000-0000-000000000001",
                _make_body(),
            )

            assert result["ok"] is True
            assert result["signal"] == "noop", (
                f"Expected 'noop' but got '{result['signal']}'. "
                "Returning 'inject' when no inject was sent is misleading."
            )
            mock_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limited_no_prompt_includes_run_id(self) -> None:
        """The noop response must include the run_id."""
        resume_run = _import_resume_run()
        run = _mock_run("rate_limited")
        run_id = "00000000-0000-0000-0000-000000000002"

        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch("backend.endpoints.runs.send_control_signal", new_callable=AsyncMock),
        ):
            result = await resume_run(run_id, _make_body())

        assert result["run_id"] == run_id

    @pytest.mark.asyncio
    async def test_rate_limited_with_prompt_still_returns_inject_signal(self) -> None:
        """When a prompt IS provided for a rate-limited run, signal 'inject' is correct."""
        resume_run = _import_resume_run()
        run = _mock_run("rate_limited")
        signals_sent: list[str] = []

        async def track_signal(run_id, signal, valid_statuses, payload, extra_body):
            signals_sent.append(signal)
            return {"ok": True, "signal": signal, "run_id": run_id}

        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch("backend.endpoints.runs.send_control_signal", side_effect=track_signal),
        ):
            result = await resume_run(
                "00000000-0000-0000-0000-000000000001",
                _make_body("keep going"),
            )

        assert result["ok"] is True
        assert signals_sent == ["inject"]
