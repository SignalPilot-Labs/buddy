"""buddy run — interactive run management with scrollable selection."""

from __future__ import annotations

import json as _json
import sys
from typing import Optional

import typer
from InquirerPy import inquirer
from rich.console import Console

from cli.client import get_client
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

app = typer.Typer(
    help="Manage agent runs — start, list, inspect, and control runs.",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


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


def _action_menu(run: dict) -> None:
    """Show an action menu for the selected run."""
    run_id = run["id"]
    status = run.get("status", "unknown")

    # Build actions based on current status
    actions: list[dict] = [{"name": "Show details", "value": "details"}]

    if status in ("running", "paused", "rate_limited"):
        if status == "running":
            actions.append({"name": "Pause", "value": "pause"})
        if status == "paused":
            actions.append({"name": "Resume", "value": "resume"})
        actions.append({"name": "Stop", "value": "stop"})
        actions.append({"name": "Inject prompt", "value": "inject"})
        actions.append({"name": "Unlock time gate", "value": "unlock"})
        actions.append({"name": "Stream live events", "value": "stream"})

    if status in ("completed", "stopped", "error"):
        actions.append({"name": "Resume (inject + restart)", "value": "inject"})

    actions.extend([
        {"name": "Tool calls", "value": "tools"},
        {"name": "Audit log", "value": "audit"},
        {"name": "Diff stats", "value": "diff"},
        {"name": "← Back", "value": "back"},
    ])

    action = inquirer.select(
        message=f"Run {short_id(run_id)} ({status}) — choose action:",
        choices=actions,
    ).execute()

    client = get_client()

    if action == "details":
        _show_run_detail(run)

    elif action == "pause":
        client.post(f"/api/runs/{run_id}/pause")
        print_success("Run paused")

    elif action == "resume":
        budget = typer.prompt("Max budget USD (0 = unlimited)", default="0", type=float)
        client.post("/api/agent/resume", json={"run_id": run_id, "max_budget_usd": budget})
        print_success("Run resumed")

    elif action == "stop":
        reason = typer.prompt("Reason", default="Operator requested stop")
        client.post(f"/api/runs/{run_id}/stop", json={"payload": reason})
        print_success("Stop signal sent")

    elif action == "inject":
        prompt = typer.prompt("Prompt to inject")
        if not prompt.strip():
            print_error("Prompt cannot be empty")
            return
        client.post(f"/api/runs/{run_id}/inject", json={"payload": prompt})
        print_success("Prompt injected")

    elif action == "unlock":
        client.post(f"/api/runs/{run_id}/unlock")
        print_success("Time gate unlocked")

    elif action == "stream":
        _stream_run(run_id)

    elif action == "tools":
        _show_tools(run_id)

    elif action == "audit":
        _show_audit(run_id)

    elif action == "diff":
        _show_diff(run_id)

    elif action == "back":
        return


def _stream_run(run_id: str) -> None:
    """Live tail SSE events for a run."""
    console.print(f"[dim]Streaming events for {short_id(run_id)}… (Ctrl+C to stop)[/dim]\n")
    try:
        for event in get_client().stream_sse(f"/api/stream/{run_id}"):
            etype = event["event"]
            data = event["data"]

            if etype == "ping":
                continue
            elif etype == "connected":
                console.print("[dim]Connected to event stream[/dim]")
            elif etype == "tool_call":
                name = data.get("tool_name", "?")
                phase = data.get("phase", "")
                dur = data.get("duration_ms")
                dur_str = f" ({dur}ms)" if dur else ""
                permitted = data.get("permitted", True)
                icon = "[green]✓[/green]" if permitted else "[red]✗[/red]"
                console.print(f"  {icon} [bold]{name}[/bold] [{phase}]{dur_str}")
            elif etype == "audit":
                et = data.get("event_type", "?")
                details = data.get("details", {})
                snippet = str(details)[:80] if details else ""
                console.print(f"  [cyan]▸[/cyan] {et}  {snippet}")
            elif etype == "run_ended":
                st = data.get("status", "unknown")
                console.print(f"\n[bold]Run ended: {status_styled(st)}[/bold]")
                return
            else:
                console.print(f"  [{etype}] {_json.dumps(data, default=str)[:100]}")
    except KeyboardInterrupt:
        console.print("\n[dim]Stream disconnected.[/dim]")


def _show_tools(run_id: str, limit: int = 50, offset: int = 0) -> None:
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


def _show_audit(run_id: str, limit: int = 50, offset: int = 0) -> None:
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


# ── Commands ────────────────────────────────────────────────────────────────


@app.command("new")
def start_run(
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", metavar="<prompt>", help="Task prompt"),
    budget: float = typer.Option(0, "--budget", "-b", metavar="<amount>", help="Max budget USD (0 = unlimited)"),
    duration: float = typer.Option(0, "--duration", "-d", metavar="<minutes>", help="Duration in minutes (0 = unlimited)"),
    base_branch: str = typer.Option("main", "--base-branch", metavar="<branch>", help="Branch to base work on"),
) -> None:
    """Start a new agent run.

    \b
    Examples:
      buddy run new -p "Fix login bugs"
      buddy run new -p "Add dark mode" -d 60 -b 5.00
      buddy run new -p "Refactor API" --base-branch develop
    """
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


@app.command("list")
def list_runs(
    repo: Optional[str] = typer.Option(None, "--repo", "-r", metavar="<owner/repo>", help="Filter by repo slug"),
) -> None:
    """List recent runs.

    \b
    Examples:
      buddy run list
      buddy run list -r owner/repo
    """
    params = {}
    if repo:
        params["repo"] = repo
    data = get_client().get("/api/runs", params=params or None)
    if state.json_mode:
        print_json(data)
        return
    rows = []
    for r in data:
        rows.append({
            "id": short_id(r.get("id", "")),
            "status": status_styled(r.get("status", "unknown")),
            "branch": r.get("branch_name", "—"),
            "repo": r.get("github_repo", "—"),
            "prompt": (r.get("custom_prompt") or "—")[:40],
            "started": relative_time(r.get("started_at")),
            "duration": format_duration(r.get("duration_minutes")),
            "cost": format_cost(r.get("total_cost_usd")),
        })
    print_table(rows, [
        ("id", "ID"), ("status", "Status"), ("branch", "Branch"),
        ("repo", "Repo"), ("prompt", "Prompt"), ("started", "Started"),
        ("duration", "Duration"), ("cost", "Cost"),
    ], title="Runs")


@app.command("get")
def get_run(
    run_id: str = typer.Argument(metavar="<run_id>", help="Run ID (UUID from 'buddy run list')"),
) -> None:
    """Show run details and open an interactive action menu (pause, stop, inject, stream, etc).

    \b
    Examples:
      buddy run get a1b2c3d4-5678-90ab-cdef-1234567890ab
    """
    run = get_client().get(f"/api/runs/{run_id}")
    if state.json_mode:
        print_json(run)
        return
    _show_run_detail(run)
    console.print()
    _action_menu(run)


@app.callback(invoke_without_command=True)
def run_callback(ctx: typer.Context) -> None:
    """Manage agent runs — start, list, inspect, and control runs.

    \b
    Run without a subcommand to open an interactive run selector:
      buddy run

    \b
    Or use a subcommand:
      buddy run new -p "Fix bugs" -d 30    Start a new run
      buddy run list                        List recent runs
      buddy run get <run_id>                Inspect a specific run
    """
    if ctx.invoked_subcommand is not None:
        return

    run = _select_run()
    if state.json_mode:
        print_json(run)
        return
    _show_run_detail(run)
    console.print()
    _action_menu(run)
