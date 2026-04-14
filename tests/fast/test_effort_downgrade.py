"""Tests for effort downgrade logic in bootstrap."""

from lifecycle.bootstrap import _build_base_session_options
from utils.models import RunContext


class TestEffortDowngrade:
    """Verify max effort is downgraded to high for models that don't support it."""

    def _make_run(self) -> RunContext:
        return RunContext(
            run_id="test-run",
            agent_role="worker",
            branch_name="test-branch",
            base_branch="main",
            duration_minutes=0,
            github_repo="owner/repo",
        )

    def test_max_effort_passes_through_for_opus(self) -> None:
        opts = _build_base_session_options(
            run=self._make_run(),
            model="opus",
            fallback_model="sonnet",
            max_budget_usd=0,
            effort="max",
            run_start_time=0.0,
        )
        assert opts["effort"] == "max"

    def test_max_effort_passes_through_for_sonnet(self) -> None:
        opts = _build_base_session_options(
            run=self._make_run(),
            model="sonnet",
            fallback_model=None,
            max_budget_usd=0,
            effort="max",
            run_start_time=0.0,
        )
        assert opts["effort"] == "max"

    def test_max_effort_downgraded_for_opus_4_5(self) -> None:
        opts = _build_base_session_options(
            run=self._make_run(),
            model="opus-4-5",
            fallback_model="sonnet",
            max_budget_usd=0,
            effort="max",
            run_start_time=0.0,
        )
        assert opts["effort"] == "high"

    def test_high_effort_unchanged_for_opus_4_5(self) -> None:
        opts = _build_base_session_options(
            run=self._make_run(),
            model="opus-4-5",
            fallback_model="sonnet",
            max_budget_usd=0,
            effort="high",
            run_start_time=0.0,
        )
        assert opts["effort"] == "high"

    def test_medium_effort_unchanged_for_all_models(self) -> None:
        for model in ("opus", "sonnet", "opus-4-5"):
            opts = _build_base_session_options(
                run=self._make_run(),
                model=model,
                fallback_model=None,
                max_budget_usd=0,
                effort="medium",
                run_start_time=0.0,
            )
            assert opts["effort"] == "medium"
