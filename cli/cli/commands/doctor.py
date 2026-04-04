"""buddy doctor — run health checks against the local Buddy setup."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx
import typer

from cli.config import resolve_api_key, resolve_api_url
from cli.constants import (
    BUDDY_HOME,
    DASHBOARD_HEALTH_URL,
    DOCTOR_HTTP_TIMEOUT_SECONDS,
    EXPECTED_COMPOSE_SERVICES,
)
from cli.git_utils import is_git_repo
from cli.output import console


@dataclass
class CheckResult:
    label: str
    ok: bool
    detail: str


class DoctorChecker:
    """Runs individual health checks against the Buddy setup."""

    def check_docker(self) -> CheckResult:
        """Check that the Docker daemon is running."""
        result = subprocess.run(["docker", "info"], capture_output=True)
        if result.returncode == 0:
            return CheckResult(label="Docker daemon", ok=True, detail="")
        return CheckResult(
            label="Docker daemon",
            ok=False,
            detail="Docker daemon is not running — start Docker Desktop and try again",
        )

    def check_containers(self) -> CheckResult:
        """Check that all expected Buddy containers are running."""
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            cwd=BUDDY_HOME,
        )
        if result.returncode != 0:
            return CheckResult(
                label="Buddy containers",
                ok=False,
                detail="docker compose failed — try: buddy start",
            )
        running = _parse_running_containers(result.stdout)
        missing = set(EXPECTED_COMPOSE_SERVICES) - running
        if not missing:
            return CheckResult(label="Buddy containers", ok=True, detail="")
        return CheckResult(
            label="Buddy containers",
            ok=False,
            detail=f"Not running: {', '.join(sorted(missing))} — try: buddy start",
        )

    def check_dashboard(self) -> CheckResult:
        """Check that the dashboard HTTP endpoint is reachable."""
        try:
            httpx.get(DASHBOARD_HEALTH_URL, timeout=DOCTOR_HTTP_TIMEOUT_SECONDS)
        except (httpx.ConnectError, httpx.TimeoutException):
            return CheckResult(
                label="Dashboard reachable",
                ok=False,
                detail=f"Dashboard not reachable at {DASHBOARD_HEALTH_URL} — try: buddy start",
            )
        return CheckResult(
            label="Dashboard reachable",
            ok=True,
            detail=f"Dashboard reachable at {DASHBOARD_HEALTH_URL}",
        )

    def check_credentials(self) -> CheckResult:
        """Check that credentials are configured and valid."""
        api_key = resolve_api_key()
        headers: dict[str, str] = {}
        if api_key is not None:
            headers["X-API-Key"] = api_key
        url = f"{resolve_api_url()}/api/settings/status"
        try:
            resp = httpx.get(url, headers=headers, timeout=DOCTOR_HTTP_TIMEOUT_SECONDS)
        except (httpx.ConnectError, httpx.TimeoutException):
            return CheckResult(
                label="Credentials configured",
                ok=False,
                detail="skipped — dashboard not reachable",
            )
        if resp.status_code == 401:
            return CheckResult(
                label="Credentials configured",
                ok=False,
                detail="API key invalid — check: buddy config get",
            )
        if resp.status_code != 200:
            return CheckResult(
                label="Credentials configured",
                ok=False,
                detail=f"Unexpected response {resp.status_code}",
            )
        return _evaluate_settings_body(resp.json())

    def check_git_repo(self) -> CheckResult:
        """Check that BUDDY_HOME is a git repository."""
        if is_git_repo(BUDDY_HOME):
            return CheckResult(label="Buddy home is git repo", ok=True, detail="")
        return CheckResult(
            label="Buddy home is git repo",
            ok=False,
            detail="~/.buddy is not a git repo — re-run the installer: curl -fsSL https://get.buddy.sh | sh",
        )


def _parse_running_containers(stdout: str) -> set[str]:
    """Parse `docker compose ps --format json` output into a set of running container names."""
    running: set[str] = set()
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        state = obj.get("State", "")
        name = obj.get("Name", "")
        if "running" in state.lower() and name:
            running.add(name)
    return running


def _evaluate_settings_body(body: dict[str, Any]) -> CheckResult:
    """Evaluate the /api/settings/status JSON body for missing credentials."""
    token_keys = ["has_claude_token", "has_git_token", "has_github_repo"]
    if body.get("configured") is True:
        return CheckResult(label="Credentials configured", ok=True, detail="")
    missing = [k.replace("has_", "") for k in token_keys if not body.get(k)]
    if missing:
        flags = ", ".join(f"buddy settings set --{m}" for m in missing)
        return CheckResult(
            label="Credentials configured",
            ok=False,
            detail=f"Missing: {', '.join(missing)} — run: {flags}",
        )
    return CheckResult(label="Credentials configured", ok=False, detail="Settings not fully configured")


def _print_check(result: CheckResult) -> None:
    if result.ok:
        console.print(f"[green][ok][/green]    {result.label}")
    else:
        console.print(f"[red][error][/red] {result.label} — {result.detail}")


def run_doctor() -> None:
    """Run all Buddy health checks and print results."""
    checker = DoctorChecker()
    results = [
        checker.check_docker(),
        checker.check_containers(),
        checker.check_dashboard(),
        checker.check_credentials(),
        checker.check_git_repo(),
    ]
    console.print("Buddy doctor\n")
    for result in results:
        _print_check(result)
    failed = [r for r in results if not r.ok]
    if failed:
        console.print("\n[yellow]Fix the issues above, then re-run buddy doctor.[/yellow]")
        raise typer.Exit(1)
    console.print("\n[green]All checks passed.[/green]")
