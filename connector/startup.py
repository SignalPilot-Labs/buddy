"""Start command execution and NDJSON event streaming.

Runs the user's start command over SSH, scans stdout for AF_QUEUED and
AF_READY markers, and yields NDJSON events to the agent.
"""

import asyncio
import json
import logging
import re

from connector.constants import AF_QUEUED_MARKER, AF_READY_MARKER
from connector.ssh import run_ssh_command, write_remote_secret

log = logging.getLogger("connector.startup")

_MARKER_RE = re.compile(r"(AF_QUEUED|AF_READY)\s+(\{.*\})")


async def stream_start_events(
    ssh_target: str,
    start_cmd: str,
    run_key: str,
    sandbox_secret: str,
    sandbox_type: str,
    host_mounts: list[dict[str, str]],
    heartbeat_timeout: int,
    secret_dir: str,
) -> tuple[asyncio.subprocess.Process, str, list[dict[str, object]]]:
    """Execute start command over SSH and collect NDJSON events.

    Returns (process, secret_file_path, events).
    """
    secret_file_path = await write_remote_secret(
        ssh_target, secret_dir, run_key, sandbox_secret,
    )

    mounts_json = json.dumps(host_mounts)
    apptainer_binds = (
        _compute_apptainer_binds(host_mounts) if sandbox_type == "slurm" else ""
    )
    docker_volumes = (
        _compute_docker_volumes(host_mounts) if sandbox_type == "docker" else ""
    )

    env = {
        "AF_RUN_KEY": run_key,
        "AF_HOST_MOUNTS_JSON": f"'{mounts_json}'",
        "AF_APPTAINER_BINDS": f"'{apptainer_binds}'" if apptainer_binds else "''",
        "AF_DOCKER_VOLUMES": f"'{docker_volumes}'" if docker_volumes else "''",
        "AF_SANDBOX_SECRET_FILE": secret_file_path,
        "AF_HEARTBEAT_TIMEOUT": str(heartbeat_timeout),
    }

    process = await run_ssh_command(ssh_target, start_cmd, env)
    events = await _collect_events(process)

    return process, secret_file_path, events


async def _collect_events(
    process: asyncio.subprocess.Process,
) -> list[dict[str, object]]:
    """Read stdout lines from process and parse marker/log events."""
    events: list[dict[str, object]] = []
    if not process.stdout:
        return events

    async for line_bytes in process.stdout:
        line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
        marker_match = _MARKER_RE.search(line)

        if marker_match:
            event = _parse_marker(marker_match)
            events.append(event)
            if event.get("event") == "ready":
                break
        else:
            events.append({"event": "log", "line": line})

    return events


def _parse_marker(match: re.Match[str]) -> dict[str, object]:
    """Parse a marker regex match into an event dict."""
    marker_name = match.group(1)
    marker_data: dict[str, object] = json.loads(match.group(2))

    if marker_name == AF_QUEUED_MARKER:
        return {"event": "queued", "backend_id": marker_data.get("backend_id")}

    if marker_name != AF_READY_MARKER:
        raise ValueError(f"Unknown marker: {marker_name}")

    event: dict[str, object] = {
        "event": "ready",
        "host": marker_data["host"],
        "port": marker_data["port"],
    }
    if "backend_id" in marker_data:
        event["backend_id"] = marker_data["backend_id"]
    return event


def _compute_apptainer_binds(mounts: list[dict[str, str]]) -> str:
    """Compute -B flags for Apptainer from mount list."""
    parts: list[str] = []
    for m in mounts:
        mode = m.get("mode", "ro")
        parts.append(f"-B {m['host_path']}:{m['container_path']}:{mode}")
    return " ".join(parts)


def _compute_docker_volumes(mounts: list[dict[str, str]]) -> str:
    """Compute -v flags for Docker from mount list."""
    parts: list[str] = []
    for m in mounts:
        mode = m.get("mode", "ro")
        parts.append(f"-v {m['host_path']}:{m['container_path']}:{mode}")
    return " ".join(parts)
