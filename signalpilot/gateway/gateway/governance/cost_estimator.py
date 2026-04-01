"""
Query cost pre-estimation — Feature #13 from the feature table.

Uses EXPLAIN to estimate query cost before execution.
Postgres: row estimates from EXPLAIN.
DuckDB: row estimates from EXPLAIN.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..connectors.base import BaseConnector


@dataclass
class CostEstimate:
    """Estimated cost of executing a query."""
    estimated_rows: int = 0
    estimated_cost: float = 0.0  # Planner cost units (not USD)
    estimated_usd: float = 0.0  # Rough USD estimate
    warning: str | None = None
    raw_plan: str | None = None

    @property
    def is_expensive(self) -> bool:
        """Heuristic: queries over $1 estimated or 1M rows are expensive."""
        return self.estimated_usd > 1.0 or self.estimated_rows > 1_000_000


# Cost per row scanned — rough heuristic for managed Postgres (RDS/Supabase)
# Based on: ~$0.10/hr for db.t3.medium, ~100K rows/sec throughput
_POSTGRES_USD_PER_ROW = 0.000_000_3  # $0.0000003 per row

# DuckDB is local/free — cost is effectively zero but we track for budgeting
_DUCKDB_USD_PER_ROW = 0.0


class CostEstimator:
    """Estimates the cost of a SQL query using EXPLAIN."""

    @staticmethod
    async def estimate_postgres(connector: BaseConnector, sql: str) -> CostEstimate:
        """Use EXPLAIN to estimate Postgres query cost."""
        try:
            # EXPLAIN with JSON output for easy parsing
            explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
            rows = await connector.execute(explain_sql)
            if not rows:
                return CostEstimate(warning="EXPLAIN returned no data")

            # Parse the EXPLAIN output
            plan_data = rows[0]
            # asyncpg returns the plan as a single column
            plan_json = None
            for val in plan_data.values():
                if isinstance(val, str):
                    plan_json = json.loads(val)
                elif isinstance(val, list):
                    plan_json = val
                break

            if not plan_json or not isinstance(plan_json, list):
                return CostEstimate(warning="Could not parse EXPLAIN output")

            plan = plan_json[0].get("Plan", {})
            total_cost = plan.get("Total Cost", 0)
            plan_rows = plan.get("Plan Rows", 0)
            estimated_usd = plan_rows * _POSTGRES_USD_PER_ROW

            return CostEstimate(
                estimated_rows=plan_rows,
                estimated_cost=total_cost,
                estimated_usd=estimated_usd,
                raw_plan=json.dumps(plan_json, indent=2)[:2000],
            )
        except Exception as e:
            return CostEstimate(warning=f"Cost estimation failed: {e}")

    @staticmethod
    async def estimate_duckdb(connector: BaseConnector, sql: str) -> CostEstimate:
        """Estimate DuckDB query cost (local, so cost is minimal)."""
        try:
            explain_sql = f"EXPLAIN {sql}"
            rows = await connector.execute(explain_sql)
            # DuckDB EXPLAIN returns text plan
            plan_text = ""
            if rows:
                first_row = rows[0]
                plan_text = str(list(first_row.values())[0]) if first_row else ""

            return CostEstimate(
                estimated_rows=0,  # DuckDB EXPLAIN doesn't easily give row count
                estimated_cost=0,
                estimated_usd=0,
                raw_plan=plan_text[:2000],
            )
        except Exception as e:
            return CostEstimate(warning=f"Cost estimation failed: {e}")

    @staticmethod
    async def estimate(connector: BaseConnector, sql: str, db_type: str) -> CostEstimate:
        """Route to the appropriate estimator based on db type."""
        if db_type == "postgres":
            return await CostEstimator.estimate_postgres(connector, sql)
        elif db_type == "duckdb":
            return await CostEstimator.estimate_duckdb(connector, sql)
        else:
            return CostEstimate(warning=f"Cost estimation not supported for {db_type}")
