"""Display helpers for run inspection: streaming, tools, audit, diff."""

from __future__ import annotations

import json as _json

from cli.client import get_client
from cli.config import state
from cli.constants import (
    AUDIT_SNIPPET_LENGTH,
    STREAM_DATA_TRUNCATION,
    STREAM_SNIPPET_LENGTH,
)
from cli.output import (
    console,
    print_json,
    print_table,
    relative_time,
    short_id,
    status_styled,
)


def stream_run(run_id: str) -> None:
    """Live tail SSE events for a run."""
    console.print(f"[dim]Streaming events for {short_id(run_id)}… (Ctrl+C to stop)[/dim]\n")
    try:
        for event in get_client().stream_sse(f"/api/stream/{run_id}"):
            _print_sse_event(event)
    except KeyboardInterrupt:
        console.print("\n[dim]Stream disconnected.[/dim]")


def _print_sse_event(event: dict) -> None:
    """Format and print a single SSE event."""
    etype = event["event"]
    data = event["data"]

    if etype == "ping":
        return
    if etype == "connected":
        console.print("[dim]Connected to event stream[/dim]")
    elif etype == "tool_call":
        _print_tool_call_event(data)
    elif etype == "audit":
        et = data.get("event_type", "?")
        details = data.get("details", {})
        snippet = str(details)[:STREAM_SNIPPET_LENGTH] if details else ""
        console.print(f"  [cyan]▸[/cyan] {et}  {snippet}")
    elif etype == "run_ended":
        st = data.get("status", "unknown")
        console.print(f"\n[bold]Run ended: {status_styled(st)}[/bold]")
    else:
        console.print(f"  [{etype}] {_json.dumps(data, default=str)[:STREAM_DATA_TRUNCATION]}")


def _print_tool_call_event(data: dict) -> None:
    """Format and print a tool_call SSE event."""
    name = data.get("tool_name", "?")
    phase = data.get("phase", "")
    dur = data.get("duration_ms")
    dur_str = f" ({dur}ms)" if dur else ""
    permitted = data.get("permitted", True)
    icon = "[green]✓[/green]" if permitted else "[red]✗[/red]"
    console.print(f"  {icon} [bold]{name}[/bold] [{phase}]{dur_str}")


def show_tools(
    run_id: str,
    limit: int,
    offset: int,
) -> None:
    """Show tool calls for a run."""
    data = get_client().get(
        f"/api/runs/{run_id}/tools",
        params={"limit": limit, "offset": offset},
    )
    if state.json_mode:
        print_json(data)
        return
    rows = []
    for tc in data:
        rows.append({
            "id": tc.get("id", ""),
            "ts": relative_time(tc.get("ts")),
            "tool": tc.get("tool_name", "?"),
            "phase": tc.get("phase", ""),
            "duration": f"{tc.get('duration_ms', '')}ms" if tc.get("duration_ms") else "—",
            "ok": "✓" if tc.get("permitted", True) else "✗",
        })
    print_table(rows, [
        ("id", "ID"), ("ts", "When"), ("tool", "Tool"),
        ("phase", "Phase"), ("duration", "Duration"), ("ok", "OK"),
    ], title=f"Tool Calls — {short_id(run_id)}")


def show_audit(
    run_id: str,
    limit: int,
    offset: int,
) -> None:
    """Show audit log for a run."""
    data = get_client().get(
        f"/api/runs/{run_id}/audit",
        params={"limit": limit, "offset": offset},
    )
    if state.json_mode:
        print_json(data)
        return
    rows = []
    for al in data:
        details = al.get("details", {})
        snippet = str(details)[:AUDIT_SNIPPET_LENGTH] if details else "—"
        rows.append({
            "id": al.get("id", ""),
            "ts": relative_time(al.get("ts")),
            "event": al.get("event_type", "?"),
            "details": snippet,
        })
    print_table(rows, [
        ("id", "ID"), ("ts", "When"), ("event", "Event"), ("details", "Details"),
    ], title=f"Audit Log — {short_id(run_id)}")


def show_diff(run_id: str) -> None:
    """Show diff stats for a run."""
    data = get_client().get(f"/api/runs/{run_id}/diff")
    if state.json_mode:
        print_json(data)
        return
    files = data.get("files", [])
    if not files:
        console.print("[dim]No file changes.[/dim]")
        return
    rows = []
    for f in files:
        added = f.get("added", 0)
        removed = f.get("removed", 0)
        bar = f"[green]+{added}[/green] [red]-{removed}[/red]"
        rows.append({
            "path": f.get("path", "?"),
            "status": f.get("status", "?"),
            "changes": bar,
        })
    print_table(rows, [("path", "File"), ("status", "Status"), ("changes", "Changes")],
                title=f"Diff — {short_id(run_id)}")
    console.print(
        f"\n  [bold]{data.get('total_files', 0)}[/bold] files  "
        f"[green]+{data.get('total_added', 0)}[/green]  "
        f"[red]-{data.get('total_removed', 0)}[/red]  "
        f"[dim](source: {data.get('source', '?')})[/dim]"
    )
