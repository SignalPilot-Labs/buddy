"""Tests for query cost estimation — Feature #13."""

import pytest

from signalpilot.gateway.gateway.governance.cost_estimator import (
    CostEstimate,
    CostEstimator,
    _POSTGRES_USD_PER_ROW,
)


class TestCostEstimate:
    """Tests for the CostEstimate dataclass."""

    def test_default_values(self):
        est = CostEstimate()
        assert est.estimated_rows == 0
        assert est.estimated_usd == 0.0
        assert est.is_expensive is False
        assert est.warning is None

    def test_is_expensive_by_usd(self):
        est = CostEstimate(estimated_usd=1.5)
        assert est.is_expensive is True

    def test_is_expensive_by_rows(self):
        est = CostEstimate(estimated_rows=2_000_000)
        assert est.is_expensive is True

    def test_not_expensive_under_threshold(self):
        est = CostEstimate(estimated_rows=500, estimated_usd=0.001)
        assert est.is_expensive is False

    def test_expensive_exactly_at_threshold(self):
        est = CostEstimate(estimated_rows=1_000_001)
        assert est.is_expensive is True

    def test_usd_threshold_boundary(self):
        est = CostEstimate(estimated_usd=0.99)
        assert est.is_expensive is False
        est2 = CostEstimate(estimated_usd=1.01)
        assert est2.is_expensive is True

    def test_with_warning(self):
        est = CostEstimate(warning="EXPLAIN returned no data")
        assert est.warning == "EXPLAIN returned no data"
        assert est.is_expensive is False

    def test_raw_plan(self):
        est = CostEstimate(raw_plan='[{"Plan": {"Total Cost": 100}}]')
        assert est.raw_plan is not None
        assert "Total Cost" in est.raw_plan


class TestCostEstimatorRouting:
    """Tests for CostEstimator.estimate() routing logic."""

    @pytest.mark.asyncio
    async def test_unsupported_db_type(self):
        """Unsupported databases should return a warning, not an error."""
        est = await CostEstimator.estimate(None, "SELECT 1", "mongodb")  # type: ignore
        assert est.warning is not None
        assert "not supported" in est.warning

    @pytest.mark.asyncio
    async def test_unsupported_snowflake(self):
        est = await CostEstimator.estimate(None, "SELECT 1", "snowflake")  # type: ignore
        assert est.warning is not None


class TestPostgresCostConstants:
    """Test cost calculation constants."""

    def test_postgres_usd_per_row_reasonable(self):
        """Verify the per-row cost constant is in a reasonable range."""
        assert 0 < _POSTGRES_USD_PER_ROW < 0.001
        # 1M rows should cost less than $1 (the expensive threshold)
        assert 1_000_000 * _POSTGRES_USD_PER_ROW < 1.0
        # 10M rows should trigger expensive threshold
        assert 10_000_000 * _POSTGRES_USD_PER_ROW > 1.0

    def test_cost_formula(self):
        """Test the USD estimation formula directly."""
        rows = 100_000
        expected_usd = rows * _POSTGRES_USD_PER_ROW
        est = CostEstimate(estimated_rows=rows, estimated_usd=expected_usd)
        assert est.estimated_usd == pytest.approx(0.03, rel=0.1)
        assert est.is_expensive is False
