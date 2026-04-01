"""
PII column tagging and result redaction — Features #14-15 from the feature table.

PII rules are defined in schema annotations (YAML sidecar files).
The redactor processes query results before they're returned to the agent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PIIRule(str, Enum):
    """Redaction strategy for PII columns."""
    hash = "hash"       # SHA-256 hash of the value
    mask = "mask"       # Partial masking (e.g., j***@email.com)
    drop = "drop"       # Remove the column entirely


@dataclass
class PIIColumnConfig:
    """Configuration for a single PII column."""
    table: str
    column: str
    rule: PIIRule
    description: str = ""


@dataclass
class PIIRedactor:
    """Redacts PII columns from query results based on configured rules.

    Rules are loaded from schema annotations (schema.yml) and keyed by
    lowercase column name for fast lookup.
    """
    # Map of lowercase column name -> rule
    _rules: dict[str, PIIRule] = field(default_factory=dict)
    # Columns that were redacted in the last call (for audit logging)
    _last_redacted: list[str] = field(default_factory=list)

    def add_rule(self, column: str, rule: PIIRule) -> None:
        """Register a PII rule for a column name."""
        self._rules[column.lower()] = rule

    def add_rules_from_annotations(self, annotations: dict[str, Any]) -> None:
        """Load PII rules from schema annotation dict.

        Expected format:
        {
            "tables": {
                "users": {
                    "columns": {
                        "email": {"pii": "hash"},
                        "ssn": {"pii": "mask"},
                        "phone": {"pii": "drop"}
                    }
                }
            }
        }
        """
        tables = annotations.get("tables", {})
        for table_name, table_config in tables.items():
            columns = table_config.get("columns", {})
            for col_name, col_config in columns.items():
                pii_rule = col_config.get("pii")
                if pii_rule and pii_rule in PIIRule.__members__:
                    self._rules[col_name.lower()] = PIIRule(pii_rule)

    def redact_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply PII redaction to a list of result rows.

        Returns new list with PII columns redacted according to their rules.
        """
        if not rows or not self._rules:
            self._last_redacted = []
            return rows

        self._last_redacted = []
        redacted_rows = []

        for row in rows:
            new_row = {}
            for col, val in row.items():
                col_lower = col.lower()
                rule = self._rules.get(col_lower)
                if rule is None:
                    new_row[col] = val
                elif rule == PIIRule.drop:
                    # Drop the column entirely
                    if col_lower not in self._last_redacted:
                        self._last_redacted.append(col_lower)
                    continue
                elif rule == PIIRule.hash:
                    new_row[col] = _hash_value(val)
                    if col_lower not in self._last_redacted:
                        self._last_redacted.append(col_lower)
                elif rule == PIIRule.mask:
                    new_row[col] = _mask_value(val)
                    if col_lower not in self._last_redacted:
                        self._last_redacted.append(col_lower)
            redacted_rows.append(new_row)

        return redacted_rows

    @property
    def last_redacted_columns(self) -> list[str]:
        """Columns that were redacted in the most recent call."""
        return list(self._last_redacted)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def has_rules(self) -> bool:
        return bool(self._rules)


def _hash_value(val: Any) -> str:
    """SHA-256 hash a value, returning first 12 chars of hex digest."""
    if val is None:
        return "NULL"
    raw = str(val).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()[:12]}"


def _mask_value(val: Any) -> str:
    """Partially mask a value, preserving structure hints."""
    if val is None:
        return "NULL"
    s = str(val)
    if not s:
        return "***"

    # Email masking: j***@email.com
    if "@" in s:
        local, domain = s.rsplit("@", 1)
        masked_local = local[0] + "***" if local else "***"
        return f"{masked_local}@{domain}"

    # Phone masking: ***-1234
    if len(s) >= 7 and any(c.isdigit() for c in s):
        return "***" + s[-4:]

    # Generic masking: first char + *** + last char
    if len(s) <= 2:
        return "***"
    return s[0] + "***" + s[-1]
