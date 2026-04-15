"""Tests that rate limit events are passed through to the SDK, not handled by AutoFyn.

The SDK handles rate limit retries internally. AutoFyn must NOT kill the
session or sleep — it should log the event, update the run status for
the frontend banner, and let the stream continue.
"""

from utils.models import RoundStatus, SignalKind, StreamSignal, RoundResult


class TestStreamSignalKind:
    """rate_limit_info signal must not end the round."""

    def test_rate_limit_info_is_valid_signal_kind(self) -> None:
        signal = StreamSignal(kind="rate_limit_info", rate_limit_data={"status": "rejected"})
        assert signal.kind == "rate_limit_info"

    def test_rate_limited_is_not_valid_signal_kind(self) -> None:
        """The old 'rate_limited' signal kind must not exist — it killed sessions."""
        assert "rate_limited" not in SignalKind.__args__  # type: ignore[attr-defined]

    def test_rate_limit_info_carries_data(self) -> None:
        data = {"status": "rejected", "resets_at": 1700000000, "utilization": 0.95}
        signal = StreamSignal(kind="rate_limit_info", rate_limit_data=data)
        assert signal.rate_limit_data == data


class TestRoundResultNoRateLimited:
    """RoundResult must not have a rate_limited status — SDK handles retries."""

    def test_rate_limited_is_not_valid_round_status(self) -> None:
        """Creating a RoundResult with status='rate_limited' must fail type checking.

        At runtime Literal validation isn't enforced by dataclasses, so we
        verify that 'rate_limited' is not in the RoundStatus type's args.
        """
        assert "rate_limited" not in RoundStatus.__args__  # type: ignore[attr-defined]

    def test_round_result_has_no_rate_limit_resets_at(self) -> None:
        """RoundResult must not carry rate_limit_resets_at — that's now in the DB directly."""
        result = RoundResult(status="complete", session_id="s1")
        assert not hasattr(result, "rate_limit_resets_at")
