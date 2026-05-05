"""Start command execution and NDJSON event streaming.

Runs the user's start command over SSH, scans stdout for AF_QUEUED and
AF_READY markers, and yields NDJSON events to the agent.
"""

import asyncio
import json
import logging
import re
import shlex
from collections.abc import AsyncGenerator
from typing import Any

from cli.connector.constants import (
    AF_BOUND_MARKER,
    AF_QUEUED_MARKER,
    AF_READY_MARKER,
    SRUN_JOB_RE_PATTERN,
)
from cli.connector.ssh import run_ssh_command

log = logging.getLogger("connector.startup")

MARKER_RE: re.Pattern[str] = re.compile(r"(AF_QUEUED|AF_READY|AF_BOUND)\s+(\{.*\})")
SRUN_JOB_RE: re.Pattern[str] = re.compile(SRUN_JOB_RE_PATTERN)


async def stream_start_events(
    ssh_target: str,
    start_cmd: str,
    run_key: str,
    sandbox_secret: str,
    sandbox_type: str,
    host_mounts: list[dict[str, str]],
    heartbeat_timeout: int,
    extra_env: dict[str, str],
) -> tuple[asyncio.subprocess.Process, AsyncGenerator[dict[str, Any], None]]:
    """Execute start command over SSH. Returns (process, event_gen).

    The sandbox secret is passed as SANDBOX_INTERNAL_SECRET env var.
    The returned async generator yields NDJSON events as they arrive.
    Callers must fully consume or close the generator.
    """
    mounts_json = json.dumps(host_mounts)
    apptainer_binds = (
        _compute_apptainer_binds(host_mounts) if sandbox_type == "slurm" else ""
    )
    docker_volumes = (
        _compute_docker_volumes(host_mounts) if sandbox_type == "docker" else ""
    )

    env = {
        "AF_RUN_KEY": run_key,
        "SANDBOX_INTERNAL_SECRET": sandbox_secret,
        "AF_HOST_MOUNTS_JSON": mounts_json,
        "AF_APPTAINER_BINDS": apptainer_binds if apptainer_binds else "",
        "AF_DOCKER_VOLUMES": docker_volumes if docker_volumes else "",
        "AF_HEARTBEAT_TIMEOUT": str(heartbeat_timeout),
    }
    env.update(extra_env)

    process = await run_ssh_command(ssh_target, start_cmd, env)
    return process, _stream_events(process, ssh_target)


async def _stream_events(
    process: asyncio.subprocess.Process,
    ssh_target: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield NDJSON events from process stdout as they arrive.

    Parses AF_* markers for structured events. Also detects srun job IDs
    from log lines (e.g. "srun: job 12345 queued") and emits them as
    queued events so the connector can scancel on destroy.
    """
    if not process.stdout:
        return

    srun_job_emitted = False
    async for line_bytes in process.stdout:
        line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
        marker_match = MARKER_RE.search(line)

        if marker_match:
            event = _parse_marker(marker_match, ssh_target)
            yield event
            if event.get("event") == "ready":
                return
        else:
            if not srun_job_emitted:
                srun_match = SRUN_JOB_RE.search(line)
                if srun_match:
                    srun_job_emitted = True
                    yield {"event": "queued", "backend_id": srun_match.group(1)}
            yield {"event": "log", "line": line}


def _parse_marker(match: re.Match[str], ssh_target: str) -> dict[str, Any]:
    """Parse a marker regex match into an event dict."""
    marker_name = match.group(1)
    marker_data: dict[str, Any] = json.loads(match.group(2))

    if marker_name == AF_QUEUED_MARKER:
        return {"event": "queued", "backend_id": marker_data.get("backend_id")}

    if marker_name == AF_BOUND_MARKER:
        # AF_BOUND only has port, no host. Do NOT promote to ready — wait
        # for AF_READY which has the actual hostname (critical for slurm
        # where the sandbox runs on a compute node, not the login node).
        return {"event": "log", "line": f"AF_BOUND port={marker_data['port']}"}

    if marker_name == AF_READY_MARKER:
        event: dict[str, Any] = {
            "event": "ready",
            "host": marker_data["host"],
            "port": marker_data["port"],
        }
        if "backend_id" in marker_data:
            event["backend_id"] = marker_data["backend_id"]
        return event

    raise ValueError(f"Unknown marker: {marker_name}")


def _compute_apptainer_binds(mounts: list[dict[str, str]]) -> str:
    """Compute -B flags for Apptainer from mount list."""
    parts: list[str] = []
    for m in mounts:
        mode = m["mode"]
        host = shlex.quote(m["host_path"])
        container = shlex.quote(m["container_path"])
        parts.append(f"-B {host}:{container}:{mode}")
    return " ".join(parts)


def _compute_docker_volumes(mounts: list[dict[str, str]]) -> str:
    """Compute -v flags for Docker from mount list."""
    parts: list[str] = []
    for m in mounts:
        mode = m["mode"]
        host = shlex.quote(m["host_path"])
        container = shlex.quote(m["container_path"])
        parts.append(f"-v {host}:{container}:{mode}")
    return " ".join(parts)
