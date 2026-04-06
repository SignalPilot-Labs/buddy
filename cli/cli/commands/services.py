"""autofyn start / stop / kill / update / logs — Docker Compose service management."""

from __future__ import annotations

import subprocess
import sys

import typer

from cli.constants import AUTOFYN_HOME, BUILD_SCRIPT, SIGINT_EXIT_CODE, UP_SCRIPT
from cli.output import console


def _compose(args: list[str]) -> None:
    """Run ``docker compose <args>`` in the AutoFyn home directory."""
    cmd = ["docker", "compose"] + args
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
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


def start_services() -> None:
    """Run up.sh — docker compose up -d only. No build."""
    _run_script(UP_SCRIPT)
    console.print("[green]✓[/green] AutoFyn services started")



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
