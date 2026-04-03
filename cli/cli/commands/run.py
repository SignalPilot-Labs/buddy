"""buddy run — interactive run management with scrollable selection."""

from __future__ import annotations

import json as _json
from typing import Callable, Optional

import typer
from InquirerPy import inquirer

from cli.client import BuddyClient, get_client
from cli.config import state
from cli.output import (
    console,
    format_cost,
    format_duration,
    print_detail,
    print_json,
    print_success,
    print_table,
    print_error,
    relative_time,
    short_id,
    status_icon,
    status_styled,
)

app = typer.Typer(help="Manage agent runs")

TOOL_LIST_LIMIT = 50
TOOL_LIST_OFFSET = 0


# ── Helpers ─────────────────────────────────────────────────────────────────


def _run_label(r: dict) -> str:
    """Build a display label for a run in the interactive list."""
    sid = short_id(r.get("id", "????????"))
    st = r.get("status", "unknown")
    prompt = (r.get("custom_prompt") or "no prompt")[:50]
    ago = relative_time(r.get("started_at"))
    icon = status_icon(st).replace("[", "").replace("]", "")  # strip Rich tags for inquirer
    # InquirerPy doesn't render Rich markup, so use plain icons
    plain_icons = {
        "running": "●", "paused": "❚❚", "completed": "✓",
        "stopped": "◼", "error": "✗", "crashed": "✗",
        "killed": "✗", "rate_limited": "⏳",
    }
    icon = plain_icons.get(st, "?")
    return f"{icon}  {sid}  {st:<13} {prompt:<52} {ago}"


def _select_run() -> dict:
    """Fetch runs and present an interactive scrollable list. Return selected run."""
    runs = get_client().get("/api/runs")
    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        raise typer.Exit(0)

    choices = [{"name": _run_label(r), "value": r["id"]} for r in runs]

    run_id = inquirer.fuzzy(
        message="Select a run:",
        choices=choices,
        max_height="70%",
    ).execute()

    if not run_id:
        raise typer.Exit(0)

    return get_client().get(f"/api/runs/{run_id}")


def _show_run_detail(run: dict) -> None:
    """Print a formatted run detail view."""
    display = {
        "ID": run.get("id", "—"),
        "Status": status_styled(run.get("status", "unknown")),
        "Branch": run.get("branch_name", "—"),
        "Base Branch": run.get("base_branch", "—"),
        "Repo": run.get("github_repo", "—"),
        "Prompt": run.get("custom_prompt", "—"),
        "Started": run.get("started_at", "—"),
        "Ended": run.get("ended_at", "—"),
        "Duration": format_duration(run.get("duration_minutes")),
        "Cost": format_cost(run.get("total_cost_usd")),
        "Tool Calls": run.get("total_tool_calls", "—"),
        "Input Tokens": f"{run.get('total_input_tokens', 0):,}",
        "Output Tokens": f"{run.get('total_output_tokens', 0):,}",
        "PR": run.get("pr_url", "—"),
        "Error": run.get("error_message") or "—",
    }
    print_detail(display, title="Run Details")


# ── Action handlers ──────────────────────────────────────────────────────────


def _handle_pause(client: BuddyClient, run_id: str) -> None:
    """Pause the run."""
    client.post(f"/api/runs/{run_id}/pause")
    print_success("Run paused")


def _handle_resume(client: BuddyClient, run_id: str) -> None:
    """Resume the run with a new budget."""
    budget = typer.prompt("Max budget USD (0 = unlimited)", type=float)
    client.post("/api/agent/resume", json={"run_id": run_id, "max_budget_usd": budget})
    print_success("Run resumed")


def _handle_stop(client: BuddyClient, run_id: str) -> None:
    """Stop the run with a reason."""
    reason = typer.prompt("Reason")
    client.post(f"/api/runs/{run_id}/stop", json={"payload": reason})
    print_success("Stop signal sent")


def _handle_inject(client: BuddyClient, run_id: str) -> None:
    """Inject a prompt into the run."""
    prompt = typer.prompt("Prompt to inject")
    if not prompt.strip():
        print_error("Prompt cannot be empty")
        return
    client.post(f"/api/runs/{run_id}/inject", json={"payload": prompt})
    print_success("Prompt injected")


def _handle_unlock(client: BuddyClient, run_id: str) -> None:
    """Unlock the time gate for the run."""
    client.post(f"/api/runs/{run_id}/unlock")
    print_success("Time gate unlocked")


_ACTION_HANDLERS: dict[str, Callable[[BuddyClient, str], None]] = {
    "pause": _handle_pause,
    "resume": _handle_resume,
    "stop": _handle_stop,
    "inject": _handle_inject,
    "unlock": _handle_unlock,
}


def _active_run_choices(status: str) -> list[dict]:
    """Return action choices specific to active (running/paused/rate_limited) runs."""
    choices: list[dict] = []
    if status == "running":
        choices.append({"name": "Pause", "value": "pause"})
    if status == "paused":
        choices.append({"name": "Resume", "value": "resume"})
    choices.extend([
        {"name": "Stop", "value": "stop"},
        {"name": "Inject prompt", "value": "inject"},
        {"name": "Unlock time gate", "value": "unlock"},
        {"name": "Stream live events", "value": "stream"},
    ])
    return choices


def _build_action_choices(status: str) -> list[dict]:
    """Build the full list of selectable actions based on run status."""
    actions: list[dict] = [{"name": "Show details", "value": "details"}]
    if status in ("running", "paused", "rate_limited"):
        actions.extend(_active_run_choices(status))
    if status in ("completed", "stopped", "error"):
        actions.append({"name": "Resume (inject + restart)", "value": "inject"})
    actions.extend([
        {"name": "Tool calls", "value": "tools"},
        {"name": "Audit log", "value": "audit"},
        {"name": "Diff stats", "value": "diff"},
        {"name": "← Back", "value": "back"},
    ])
    return actions


def _action_menu(run: dict) -> None:
    """Show an action menu for the selected run."""
    run_id = run["id"]
    status = run.get("status", "unknown")
    actions = _build_action_choices(status)
    action = inquirer.select(
        message=f"Run {short_id(run_id)} ({status}) — choose action:",
        choices=actions,
    ).execute()
    _dispatch_action(action, run, run_id)


def _dispatch_action(action: str, run: dict, run_id: str) -> None:
    """Dispatch the selected action to the appropriate handler."""
    client = get_client()
    if action == "details":
        _show_run_detail(run)
    elif action in _ACTION_HANDLERS:
        _ACTION_HANDLERS[action](client, run_id)
    elif action == "stream":
        _stream_run(run_id)
    elif action == "tools":
        _show_tools(run_id, TOOL_LIST_LIMIT, TOOL_LIST_OFFSET)
    elif action == "audit":
        _show_audit(run_id, TOOL_LIST_LIMIT, TOOL_LIST_OFFSET)
    elif action == "diff":
        _show_diff(run_id)


def _dispatch_stream_event(etype: str, data: dict) -> bool:
    """Handle a single SSE event; return True when stream should stop."""
    if etype == "ping":
        return False
    if etype == "connected":
        console.print("[dim]Connected to event stream[/dim]")
    elif etype == "tool_call":
        _print_tool_call_event(data)
    elif etype == "audit":
        _print_audit_event(data)
    elif etype == "run_ended":
        st = data.get("status", "unknown")
        console.print(f"\n[bold]Run ended: {status_styled(st)}[/bold]")
        return True
    else:
        console.print(f"  [{etype}] {_json.dumps(data, default=str)[:100]}")
    return False


def _stream_run(run_id: str) -> None:
    """Live tail SSE events for a run."""
    console.print(f"[dim]Streaming events for {short_id(run_id)}… (Ctrl+C to stop)[/dim]\n")
    try:
        for event in get_client().stream_sse(f"/api/stream/{run_id}"):
            if _dispatch_stream_event(event["event"], event["data"]):
                return
    except KeyboardInterrupt:
        console.print("\n[dim]Stream disconnected.[/dim]")


def _print_tool_call_event(data: dict) -> None:
    """Print a formatted tool_call SSE event."""
    name = data.get("tool_name", "?")
    phase = data.get("phase", "")
    dur = data.get("duration_ms")
    dur_str = f" ({dur}ms)" if dur else ""
    permitted = data.get("permitted", True)
    icon = "[green]✓[/green]" if permitted else "[red]✗[/red]"
    console.print(f"  {icon} [bold]{name}[/bold] [{phase}]{dur_str}")


def _print_audit_event(data: dict) -> None:
    """Print a formatted audit SSE event."""
    et = data.get("event_type", "?")
    details = data.get("details", {})
    snippet = str(details)[:80] if details else ""
    console.print(f"  [cyan]▸[/cyan] {et}  {snippet}")


def _show_tools(run_id: str, limit: int, offset: int) -> None:
    """Show tool calls for a run."""
    data = get_client().get(f"/api/runs/{run_id}/tools", params={"limit": limit, "offset": offset})
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


def _show_audit(run_id: str, limit: int, offset: int) -> None:
    """Show audit log for a run."""
    data = get_client().get(f"/api/runs/{run_id}/audit", params={"limit": limit, "offset": offset})
    if state.json_mode:
        print_json(data)
        return
    rows = []
    for al in data:
        details = al.get("details", {})
        snippet = str(details)[:60] if details else "—"
        rows.append({
            "id": al.get("id", ""),
            "ts": relative_time(al.get("ts")),
            "event": al.get("event_type", "?"),
            "details": snippet,
        })
    print_table(rows, [
        ("id", "ID"), ("ts", "When"), ("event", "Event"), ("details", "Details"),
    ], title=f"Audit Log — {short_id(run_id)}")


def _format_diff_rows(files: list[dict]) -> list[dict]:
    """Convert file diff entries into display rows."""
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
    return rows


def _print_diff_summary(data: dict) -> None:
    """Print the summary line of a diff response."""
    console.print(
        f"\n  [bold]{data.get('total_files', 0)}[/bold] files  "
        f"[green]+{data.get('total_added', 0)}[/green]  "
        f"[red]-{data.get('total_removed', 0)}[/red]  "
        f"[dim](source: {data.get('source', '?')})[/dim]"
    )


def _show_diff(run_id: str) -> None:
    """Show diff stats for a run."""
    data = get_client().get(f"/api/runs/{run_id}/diff")
    if state.json_mode:
        print_json(data)
        return
    files = data.get("files", [])
    if not files:
        console.print("[dim]No file changes.[/dim]")
        return
    rows = _format_diff_rows(files)
    print_table(rows, [("path", "File"), ("status", "Status"), ("changes", "Changes")],
                title=f"Diff — {short_id(run_id)}")
    _print_diff_summary(data)


# ── Commands ────────────────────────────────────────────────────────────────


@app.command("start")
def start_run(
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Task prompt"),
    budget: float = typer.Option(0, "--budget", "-b", help="Max budget USD (0 = unlimited)"),
    duration: float = typer.Option(0, "--duration", "-d", help="Duration in minutes (0 = unlimited)"),
    base_branch: str = typer.Option("main", "--base-branch", help="Branch to base work on"),
) -> None:
    """Start a new agent run."""
    body = {
        "prompt": prompt,
        "max_budget_usd": budget,
        "duration_minutes": duration,
        "base_branch": base_branch,
    }
    data = get_client().post("/api/agent/start", json=body)
    if state.json_mode:
        print_json(data)
        return
    run_id = data.get("run_id", data.get("id", ""))
    print_success(f"Run started: {run_id}")


def _resolve_run(run_id: Optional[str]) -> dict:
    """Fetch a run by ID or interactively select one."""
    if run_id:
        return get_client().get(f"/api/runs/{run_id}")
    return _select_run()


@app.callback(invoke_without_command=True)
def run_callback(
    ctx: typer.Context,
    run_id: Optional[str] = typer.Argument(None, help="Run ID (omit for interactive selection)"),
) -> None:
    """Manage runs. Omit run_id for an interactive selector."""
    if ctx.invoked_subcommand is not None:
        return
    run = _resolve_run(run_id)
    if state.json_mode:
        print_json(run)
        return
    _show_run_detail(run)
    console.print()
    _action_menu(run)
