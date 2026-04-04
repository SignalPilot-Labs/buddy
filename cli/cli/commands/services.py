"""buddy start / stop / kill — Docker Compose service management."""

from __future__ import annotations

import os
import subprocess
import sys

import typer
from rich.console import Console

from cli.config import resolve_project_dir

console = Console()


def _detect_host_ip() -> str | None:
    """Detect the host machine's LAN IP (macOS or Linux)."""
    for cmd in (["ipconfig", "getifaddr", "en0"], ["hostname", "-I"]):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split()[0]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


def _compose(args: list[str], *, project_dir: str | None = None) -> None:
    """Run ``docker compose <args>`` in the project directory, streaming output."""
    cwd = project_dir or resolve_project_dir()
    cmd = ["docker", "compose"] + args
    console.print(f"[dim]→ {' '.join(cmd)}  (in {cwd})[/dim]")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def start_services() -> None:
    """Start all Buddy services."""
    if not os.environ.get("HOST_IP"):
        host_ip = _detect_host_ip()
        if host_ip:
            os.environ["HOST_IP"] = host_ip
            console.print(f"[dim]Host IP: {host_ip}[/dim]")
    _compose(["up", "--build", "-d"])
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
