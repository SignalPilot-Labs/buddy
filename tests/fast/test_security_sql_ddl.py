"""Regression tests for f-string SQL DDL interpolation vulnerability in db/connection.py.

Verifies:
  1. No f-string DDL in connection.py (static analysis).
  2. validate_sql_identifier accepts all allowlisted values.
  3. validate_sql_identifier rejects SQL injection attempts.
  4. validate_sql_identifier rejects valid-looking but unlisted identifiers.
  5. VALID_CONTROL_SIGNALS matches the CheckConstraint in the ControlSignal model.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint

from db.constants import (
    MIGRATION_CACHE_TOKEN_COLUMNS,
    VALID_CONTROL_SIGNALS,
    validate_sql_identifier,
)
from db.models import ControlSignal


CONNECTION_PY = Path(__file__).parent.parent.parent / "db" / "connection.py"

DDL_KEYWORDS: tuple[str, ...] = ("ALTER TABLE", "ADD COLUMN", "ADD CONSTRAINT")


class TestSqlDdlSafety:
    """Regression tests for SQL DDL injection via f-string interpolation."""

    def test_no_fstring_ddl_in_connection(self) -> None:
        """No f-string in db/connection.py must contain DDL keywords.

        Static analysis catches future regressions where validated construction
        is accidentally reverted to f-string interpolation.
        """
        content = CONNECTION_PY.read_text()
        # Match f-strings: f"..." or f'...' — look for DDL keywords inside them.
        fstring_pattern = re.compile(r'f["\']([^"\']*)["\']', re.DOTALL)
        for match in fstring_pattern.finditer(content):
            body = match.group(1)
            for keyword in DDL_KEYWORDS:
                assert keyword not in body, (
                    f"Found DDL keyword {keyword!r} inside an f-string in connection.py. "
                    "Use validate_sql_identifier() and string concatenation instead."
                )

    def test_validate_sql_identifier_accepts_allowlisted(self) -> None:
        """validate_sql_identifier must accept every value in the two allowlists."""
        for signal in VALID_CONTROL_SIGNALS:
            result = validate_sql_identifier(signal, VALID_CONTROL_SIGNALS)
            assert result == signal

        for col in MIGRATION_CACHE_TOKEN_COLUMNS:
            result = validate_sql_identifier(col, MIGRATION_CACHE_TOKEN_COLUMNS)
            assert result == col

    def test_validate_sql_identifier_rejects_injection(self) -> None:
        """validate_sql_identifier must reject SQL injection payloads."""
        injection_payloads = (
            "col; DROP TABLE runs--",
            "col\nDROP",
            "Robert'); DROP TABLE runs;--",
            "' OR '1'='1",
            "pause; DELETE FROM control_signals--",
        )
        for payload in injection_payloads:
            with pytest.raises(ValueError):
                validate_sql_identifier(payload, VALID_CONTROL_SIGNALS)

    def test_validate_sql_identifier_rejects_unlisted(self) -> None:
        """validate_sql_identifier must reject a safe-looking but unlisted identifier.

        This verifies the allowlist is the primary gate — not just the regex.
        A syntactically valid identifier must still be in the allowlist.
        """
        with pytest.raises(ValueError):
            validate_sql_identifier("harmless_column", VALID_CONTROL_SIGNALS)

        with pytest.raises(ValueError):
            validate_sql_identifier("harmless_column", MIGRATION_CACHE_TOKEN_COLUMNS)

    def test_signals_constant_matches_model_constraint(self) -> None:
        """VALID_CONTROL_SIGNALS must match the CheckConstraint in the ControlSignal model.

        Verifies that models.py and constants.py stay in sync: every signal
        from the constant must appear in the constraint text and vice versa.
        """
        # Extract the check constraint text from the model's table args.
        constraint_text: str | None = None
        for arg in ControlSignal.__table_args__:
            if isinstance(arg, CheckConstraint):
                constraint_text = str(arg.sqltext)
                break

        assert constraint_text is not None, "ControlSignal must have a CheckConstraint"

        for signal in VALID_CONTROL_SIGNALS:
            assert signal in constraint_text, (
                f"Signal {signal!r} from VALID_CONTROL_SIGNALS not found in CheckConstraint: {constraint_text!r}"
            )

        # Also verify no extra signals appear in the constraint.
        # Extract quoted strings from constraint text.
        quoted_in_constraint = set(re.findall(r"'([^']+)'", constraint_text))
        for signal in quoted_in_constraint:
            assert signal in VALID_CONTROL_SIGNALS, (
                f"Signal {signal!r} in CheckConstraint is not in VALID_CONTROL_SIGNALS"
            )
