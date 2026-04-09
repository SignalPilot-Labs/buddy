"""autofyn start / stop / kill / update / logs — Docker Compose service management."""

from __future__ import annotations

import os
import subprocess
import sys

import typer

from cli.constants import AUTOFYN_HOME, BUILD_SCRIPT, SIGINT_EXIT_CODE, UP_SCRIPT
from cli.output import console


def _compose(args: list[str]) -> None:
    """Run ``docker compose <args>`` in the AutoFyn home directory."""
    cmd = ["docker", "compose"] + args
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    os.environ.setdefault("AGENT_INTERNAL_SECRET", "default")
    result = subprocess.run(cmd, cwd=AUTOFYN_HOME)
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def _run_script(script_path: str) -> None:
    """Execute a shell script and exit on failure."""
    console.print(f"[dim]→ bash {script_path}[/dim]")
    result = subprocess.run(["bash", script_path])
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def _git_pull() -> None:
    """Run git pull in AUTOFYN_HOME to update the installation."""
    console.print(f"[dim]→ git pull in {AUTOFYN_HOME}[/dim]")
    result = subprocess.run(["git", "pull"], cwd=AUTOFYN_HOME)
    if result.returncode != 0:
        console.print(f"[red]git pull exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def build_services() -> None:
    """Run build.sh — docker compose build only."""
    _run_script(BUILD_SCRIPT)
    console.print("[green]✓[/green] AutoFyn images built")


_DOCKER_WARNING = (
    "[bold yellow]⚠ WARNING:[/bold yellow] --allow-docker grants the agent "
    "[bold]full access to the host Docker daemon[/bold].\n"
    "  The agent can create, inspect, and remove any container on this machine.\n"
    "  Only use this if you trust the prompts you send.\n"
)


def start_services(allow_docker: bool) -> None:
    """Run up.sh — tears down stale containers then docker compose up -d."""
    if allow_docker:
        console.print(_DOCKER_WARNING)
        os.environ["AF_ALLOW_DOCKER"] = "1"
    _run_script(UP_SCRIPT)
    console.print("[green]✓[/green] AutoFyn services started")
    _ensure_tokens()


def _ensure_tokens() -> None:
    """Check for missing tokens and offer to auto-detect from CLI tools."""
    from cli.client import get_client

    client = get_client()
    try:
        status = client.get("/api/settings/status")
    except SystemExit:
        console.print("[yellow]Dashboard not reachable yet — set tokens manually via: autofyn settings set[/yellow]")
        return

    if status["configured"]:
        return

    updates: dict[str, str] = {}

    if not status["has_claude_token"]:
        token = _detect_claude_token()
        if token:
            updates["claude_token"] = token

    if not status["has_git_token"]:
        token = _detect_git_token()
        if token:
            updates["git_token"] = token

    if updates:
        try:
            client.put("/api/settings", json=updates)
            console.print(
                f"[green]✓[/green] Saved {', '.join(updates.keys())} to settings"
            )
        except SystemExit:
            console.print("[yellow]Failed to save tokens — set them manually via settings[/yellow]")


def _run_token_cmd(cmd: list[str]) -> str | None:
    """Run a command and return stdout, or None if it fails or isn't installed."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def _detect_claude_token() -> str | None:
    """Get Claude OAuth token via `claude setup-token` (interactive OAuth flow)."""
    console.print("\n[bold]Claude OAuth Token[/bold]")
    if typer.confirm("Run `claude setup-token` to authenticate via browser?", default=True):
        try:
            result = subprocess.run(
                ["claude", "setup-token"], capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                token = result.stdout.strip().splitlines()[-1]
                console.print(f"[green]✓[/green] Token received ({token[:12]}****)")
                return token
        except FileNotFoundError:
            console.print("[yellow]claude CLI not installed. Install it: npm install -g @anthropic-ai/claude-code[/yellow]")
    console.print("[dim]Paste your token below, or press enter to skip.[/dim]")
    entered = typer.prompt("Claude OAuth token (enter to skip)", default="", hide_input=True)
    return entered if entered.strip() else None


def _detect_git_token() -> str | None:
    """Try to get GitHub token via `gh auth token`."""
    console.print("\n[bold]GitHub Personal Access Token[/bold]")
    console.print("[dim]Checking gh CLI for an existing token...[/dim]")
    token = _run_token_cmd(["gh", "auth", "token"])
    if token:
        masked = token[:7] + "****"
        if typer.confirm(f"Found token from gh CLI ({masked}). Use it?", default=True):
            return token
    console.print("[dim]No token found. Run `gh auth login` to authenticate, or paste one below.[/dim]")
    entered = typer.prompt("GitHub token (enter to skip)", default="", hide_input=True)
    return entered if entered.strip() else None


def update_services() -> None:
    """Update: git pull in AUTOFYN_HOME then rebuild."""
    _git_pull()
    build_services()


def show_logs(tail_lines: int) -> None:
    """Stream Docker Compose logs with optional tail.

    Ctrl+C (SIGINT) is a normal exit for log streaming, so exit code 130
    is silently swallowed instead of printing an error.
    """
    cmd = ["docker", "compose", "logs", "--tail", str(tail_lines), "-f"]
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=AUTOFYN_HOME)
    if result.returncode != 0 and result.returncode != SIGINT_EXIT_CODE:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def stop_services() -> None:
    """Stop all AutoFyn services."""
    _compose(["down"])
    console.print("[green]✓[/green] AutoFyn services stopped")


def kill_services() -> None:
    """Force-remove all AutoFyn containers and volumes."""
    typer.confirm(
        "This will remove all AutoFyn containers. Continue?",
        abort=True,
    )
    _compose(["down"])
    console.print("[green]✓[/green] AutoFyn containers removed")
