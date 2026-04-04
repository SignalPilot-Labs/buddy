"""buddy start / stop / kill — Docker Compose service management."""

from __future__ import annotations

import subprocess
import sys

import typer
from rich.console import Console

from cli.constants import BUDDY_HOME, START_SCRIPT

console = Console()


def _compose(args: list[str]) -> None:
    """Run ``docker compose <args>`` in the Buddy home directory."""
    cmd = ["docker", "compose"] + args
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=BUDDY_HOME)
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def start_services() -> None:
    """Start all Buddy services via start.sh."""
    console.print("[dim]→ bash start.sh -d[/dim]")
    result = subprocess.run(["bash", START_SCRIPT, "-d"])
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)
    console.print("[green]✓[/green] Buddy services started")


def stop_services() -> None:
    """Stop all Buddy services."""
    _compose(["stop"])
    console.print("[green]✓[/green] Buddy services stopped")


def kill_services() -> None:
    """Force-remove all Buddy containers and volumes."""
    typer.confirm(
        "This will remove all Buddy containers. Continue?",
        abort=True,
    )
    _compose(["down"])
    console.print("[green]✓[/green] Buddy containers removed")
