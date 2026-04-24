"""Output helpers — Rich tables, JSON mode, status colours, formatters."""

from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from typing import Any, Sequence

from rich.console import Console
from rich.table import Table

from cli.config import state
from cli.constants import MASK_PREFIX_DEFAULT, SHORT_ID_LENGTH

console = Console()

# Status → Rich colour mapping
_STATUS_COLOURS: dict[str, str] = {
    "running": "green",
    "paused": "yellow",
    "completed": "blue",
    "stopped": "red",
    "error": "red",
    "crashed": "red",
    "killed": "red",
    "rate_limited": "magenta",
}

_STATUS_ICONS: dict[str, str] = {
    "running": "●",
    "paused": "❚❚",
    "completed": "✓",
    "stopped": "◼",
    "error": "✗",
    "crashed": "✗",
    "killed": "✗",
    "rate_limited": "⏳",
}


def status_styled(status: str) -> str:
    """Return *status* wrapped in a Rich colour tag."""
    colour = _STATUS_COLOURS.get(status, "white")
    return f"[{colour}]{status}[/{colour}]"


def status_icon(status: str) -> str:
    """Return a coloured icon for *status*."""
    colour = _STATUS_COLOURS.get(status, "white")
    icon = _STATUS_ICONS.get(status, "?")
    return f"[{colour}]{icon}[/{colour}]"


def plain_status_icon(status: str) -> str:
    """Return the plain (no Rich tags) icon for *status*."""
    return _STATUS_ICONS.get(status, "?")


def format_duration(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    if minutes == 0:
        return "unlimited"
    if minutes < 60:
        return f"{minutes:.0f}m"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}h{mins}m" if mins else f"{hours}h"


def format_cost(usd: float | None) -> str:
    if usd is None:
        return "—"
    return f"${usd:.2f}"


def relative_time(iso_str: str | None) -> str:
    """Turn an ISO timestamp into a human-friendly relative string."""
    if not iso_str:
        return "—"
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def short_id(run_id: str) -> str:
    """First 8 chars of a UUID."""
    return run_id[:SHORT_ID_LENGTH]


# ── Secret masking ──────────────────────────────────────────────────────────


def mask_secret(value: str, prefix_len: int) -> str:
    """Mask a secret, showing only the first *prefix_len* characters.

    Mirrors dashboard/backend/crypto.py::mask byte-for-byte so CLI-local
    masking and server-side masking render identically.
    """
    if not value:
        return ""
    if len(value) <= prefix_len:
        return "****"
    return value[:prefix_len] + "*" * (len(value) - prefix_len)


def _redact_dict(data: dict, secret_keys: frozenset[str], prefix_len: int) -> dict:
    """Shallow copy of *data* with values of *secret_keys* masked.

    Only ever called on dicts.
    """
    out: dict = {}
    for k, v in data.items():
        if k in secret_keys and v is not None:
            out[k] = mask_secret(str(v), prefix_len)
        else:
            out[k] = v
    return out


# ── Output functions ────────────────────────────────────────────────────────


def print_json(
    data: Any,
    *,
    secret_keys: frozenset[str] | None = None,
    prefix_len: int = MASK_PREFIX_DEFAULT,
) -> None:
    """Pretty-print data as JSON, optionally masking secret fields."""
    payload = data
    if secret_keys is not None and isinstance(payload, dict):
        payload = _redact_dict(payload, secret_keys, prefix_len)
    console.print_json(_json.dumps(payload, default=str))


def print_table(
    rows: Sequence[dict],
    columns: list[tuple[str, str]],
    *,
    title: str | None = None,
) -> None:
    """Render *rows* as a Rich table.

    *columns* is a list of ``(dict_key, header_label)`` tuples.
    """
    if state.json_mode:
        print_json(list(rows))
        return

    table = Table(title=title, show_lines=False, pad_edge=False)
    for _, header in columns:
        table.add_column(header)
    for row in rows:
        table.add_row(*(str(row.get(k, "")) for k, _ in columns))
    console.print(table)


def print_detail(
    data: dict,
    *,
    title: str | None = None,
    secret_keys: frozenset[str] | None = None,
    prefix_len: int = MASK_PREFIX_DEFAULT,
) -> None:
    """Render a single record as a key → value table, optionally masking secrets."""
    rendered: dict = data if secret_keys is None else _redact_dict(data, secret_keys, prefix_len)
    if state.json_mode:
        print_json(rendered)
        return

    table = Table(title=title, show_header=False, show_lines=False, pad_edge=False)
    table.add_column("Key", style="bold")
    table.add_column("Value")
    for k, v in rendered.items():
        table.add_row(k, str(v) if v is not None else "—")
    console.print(table)


def print_success(msg: str) -> None:
    console.print(f"[green]✓[/green] {msg}")


def print_error(msg: str) -> None:
    console.print(f"[red]✗[/red] {msg}")
