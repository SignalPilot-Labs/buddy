"""autofyn run — interactive run management with scrollable selection."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from InquirerPy import inquirer

from cli.client import get_client
from cli.git import detect_local_repo
from cli.commands.run_helpers import show_audit, show_diff, show_tools, stream_run
from cli.config import state
from cli.constants import (
    DEFAULT_BASE_BRANCH,
    DEFAULT_QUERY_LIMIT,
    DEFAULT_QUERY_OFFSET,
    DEFAULT_RUN_BUDGET,
    DEFAULT_RUN_DURATION,
    FUZZY_MAX_HEIGHT,
    PROMPT_LIST_TRUNCATION,
    PROMPT_SELECTOR_TRUNCATION,
    RUN_LABEL_PROMPT_WIDTH,
    RUN_LABEL_STATUS_WIDTH,
)
from cli.output import (
    console,
    format_cost,
    format_duration,
    plain_status_icon,
    print_detail,
    print_error,
    print_json,
    print_success,
    print_table,
    relative_time,
    short_id,
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
    prompt = (r.get("custom_prompt") or "no prompt")[:PROMPT_SELECTOR_TRUNCATION]
    ago = relative_time(r.get("started_at"))
    icon = plain_status_icon(st)
    return f"{icon}  {sid}  {st:<{RUN_LABEL_STATUS_WIDTH}} {prompt:<{RUN_LABEL_PROMPT_WIDTH}} {ago}"


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
        max_height=FUZZY_MAX_HEIGHT,
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


def _resolve_repo_for_run() -> str | None:
    """Detect local git repo and sync with server active repo."""
    slug = detect_local_repo(Path.cwd())
    if slug is None:
        return None

    settings = get_client().get("/api/settings")
    server_repo = settings.get("github_repo")

    if not server_repo:
        get_client().put("/api/repos/active", json={"repo": slug})
        console.print(f"[green]Auto-set active repo to {slug}[/green]")
    elif server_repo == slug:
        console.print(f"[dim]Repo matches server: {slug}[/dim]")
    else:
        console.print(
            f"[yellow]Active repo is {server_repo} but you're in {slug}[/yellow]"
        )

    return slug


def _action_menu(run: dict) -> None:
    """Show an action menu for the selected run, looping until 'back'."""
    while True:
        run_id = run["id"]
        status = run.get("status", "unknown")

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

        actions.extend(
            [
                {"name": "Tool calls", "value": "tools"},
                {"name": "Audit log", "value": "audit"},
                {"name": "Diff stats", "value": "diff"},
                {"name": "← Back", "value": "back"},
            ]
        )

        action = inquirer.select(
            message=f"Run {short_id(run_id)} ({status}) — choose action:",
            choices=actions,
        ).execute()

        if action == "back":
            break

        _dispatch_action(action, run)
        run = get_client().get(f"/api/runs/{run_id}")


def _dispatch_action(action: str, run: dict) -> None:
    """Execute the chosen action menu item."""
    run_id = run["id"]
    client = get_client()

    if action == "details":
        _show_run_detail(run)
    elif action == "pause":
        client.post(f"/api/runs/{run_id}/pause")
        print_success("Run paused")
    elif action == "resume":
        client.post(f"/api/runs/{run_id}/resume", json={})
        print_success("Run resumed")
    elif action == "stop":
        reason = typer.prompt("Reason", default="User requested stop")
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
        stream_run(run_id)
    elif action == "tools":
        show_tools(run_id, DEFAULT_QUERY_LIMIT, DEFAULT_QUERY_OFFSET)
    elif action == "audit":
        show_audit(run_id, DEFAULT_QUERY_LIMIT, DEFAULT_QUERY_OFFSET)
    elif action == "diff":
        show_diff(run_id)


# ── Commands ────────────────────────────────────────────────────────────────


@app.command("new")
def start_run(
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p", metavar="<prompt>", help="Task prompt"
    ),
    budget: float = typer.Option(
        DEFAULT_RUN_BUDGET,
        "--budget",
        "-b",
        metavar="<amount>",
        help="Max budget USD (0 = unlimited)",
    ),
    duration: float = typer.Option(
        DEFAULT_RUN_DURATION,
        "--duration",
        "-d",
        metavar="<minutes>",
        help="Duration in minutes (0 = unlimited)",
    ),
    base_branch: str = typer.Option(
        DEFAULT_BASE_BRANCH,
        "--base-branch",
        metavar="<branch>",
        help="Branch to base work on",
    ),
) -> None:
    """Start a new agent run.

    \b
    Examples:
      autofyn run new -p "Fix login bugs"
      autofyn run new -p "Add dark mode" -d 60 -b 5.00
      autofyn run new -p "Refactor API" --base-branch develop
    """
    _resolve_repo_for_run()
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
    repo: Optional[str] = typer.Option(
        None, "--repo", "-r", metavar="<owner/repo>", help="Filter by repo slug"
    ),
) -> None:
    """List recent runs.

    \b
    Examples:
      autofyn run list
      autofyn run list -r owner/repo
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
        rows.append(
            {
                "id": short_id(r.get("id", "")),
                "status": status_styled(r.get("status", "unknown")),
                "branch": r.get("branch_name", "—"),
                "repo": r.get("github_repo", "—"),
                "prompt": (r.get("custom_prompt") or "—")[:PROMPT_LIST_TRUNCATION],
                "started": relative_time(r.get("started_at")),
                "duration": format_duration(r.get("duration_minutes")),
                "cost": format_cost(r.get("total_cost_usd")),
            }
        )
    print_table(
        rows,
        [
            ("id", "ID"),
            ("status", "Status"),
            ("branch", "Branch"),
            ("repo", "Repo"),
            ("prompt", "Prompt"),
            ("started", "Started"),
            ("duration", "Duration"),
            ("cost", "Cost"),
        ],
        title="Runs",
    )


@app.command("get")
def get_run(
    run_id: str = typer.Argument(
        metavar="<run_id>", help="Run ID (UUID from 'autofyn run list')"
    ),
) -> None:
    """Show run details and open an interactive action menu (pause, stop, inject, stream, etc).

    \b
    Examples:
      autofyn run get a1b2c3d4-5678-90ab-cdef-1234567890ab
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
      autofyn run

    \b
    Or use a subcommand:
      autofyn run new -p "Fix bugs" -d 30    Start a new run
      autofyn run list                        List recent runs
      autofyn run get <run_id>                Inspect a specific run
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
