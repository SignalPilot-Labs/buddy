"""Dashboard API endpoints — remote sandbox CRUD."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from backend import auth
from backend.utils import session, upsert_setting
from db.constants import (
    ACTIVE_RUN_STATUSES,
    VALID_SANDBOX_TYPES,
)
from db.models import Run, Setting

log = logging.getLogger("dashboard.sandboxes")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

REMOTE_SANDBOX_KEY_PREFIX: str = "remote_sandbox:"
LAST_START_CMD_KEY_PREFIX: str = "last_start_cmd:"
REMOTE_MOUNTS_KEY_PREFIX: str = "remote_mounts:"
DEFAULT_SECRET_DIR: str = "~/.autofyn/secrets"

SANDBOX_NAME_MIN_LEN: int = 1
SANDBOX_NAME_MAX_LEN: int = 256
SSH_TARGET_MIN_LEN: int = 1
SSH_TARGET_MAX_LEN: int = 512
START_CMD_MIN_LEN: int = 1
START_CMD_MAX_LEN: int = 65536
SECRET_DIR_MAX_LEN: int = 4096
QUEUE_TIMEOUT_MIN: int = 60
QUEUE_TIMEOUT_MAX: int = 86400
HEARTBEAT_TIMEOUT_MIN: int = 60
HEARTBEAT_TIMEOUT_MAX: int = 86400

SANDBOX_TYPE_PATTERN: str = f"^({'|'.join(VALID_SANDBOX_TYPES)})$"


class RemoteSandboxConfig(BaseModel):
    """Request body for creating/updating a remote sandbox config."""

    name: str = Field(min_length=SANDBOX_NAME_MIN_LEN, max_length=SANDBOX_NAME_MAX_LEN)
    ssh_target: str = Field(min_length=SSH_TARGET_MIN_LEN, max_length=SSH_TARGET_MAX_LEN)
    type: str = Field(pattern=SANDBOX_TYPE_PATTERN)
    default_start_cmd: str = Field(min_length=START_CMD_MIN_LEN, max_length=START_CMD_MAX_LEN)
    secret_dir: str = Field(max_length=SECRET_DIR_MAX_LEN)
    queue_timeout: int = Field(ge=QUEUE_TIMEOUT_MIN, le=QUEUE_TIMEOUT_MAX)
    heartbeat_timeout: int = Field(ge=HEARTBEAT_TIMEOUT_MIN, le=HEARTBEAT_TIMEOUT_MAX)


class RemoteSandboxResponse(BaseModel):
    """Response for a single remote sandbox config."""

    id: str
    name: str
    ssh_target: str
    type: str
    default_start_cmd: str
    secret_dir: str
    queue_timeout: int
    heartbeat_timeout: int


def _setting_key(sandbox_id: str) -> str:
    """Build the settings table key for a remote sandbox config."""
    return f"{REMOTE_SANDBOX_KEY_PREFIX}{sandbox_id}"


def _parse_config(setting: Setting) -> RemoteSandboxResponse:
    """Parse a Setting row into a RemoteSandboxResponse."""
    sandbox_id = setting.key.removeprefix(REMOTE_SANDBOX_KEY_PREFIX)
    data: dict = json.loads(setting.value)
    return RemoteSandboxResponse(
        id=sandbox_id,
        name=data["name"],
        ssh_target=data["ssh_target"],
        type=data["type"],
        default_start_cmd=data["default_start_cmd"],
        secret_dir=data["secret_dir"],
        queue_timeout=data["queue_timeout"],
        heartbeat_timeout=data["heartbeat_timeout"],
    )


def _config_to_dict(body: RemoteSandboxConfig) -> dict[str, str | int]:
    """Convert a RemoteSandboxConfig to a serializable dict."""
    return {
        "name": body.name,
        "ssh_target": body.ssh_target,
        "type": body.type,
        "default_start_cmd": body.default_start_cmd,
        "secret_dir": body.secret_dir or DEFAULT_SECRET_DIR,
        "queue_timeout": body.queue_timeout,
        "heartbeat_timeout": body.heartbeat_timeout,
    }


@router.get("/sandboxes")
async def list_sandboxes() -> list[RemoteSandboxResponse]:
    """List all remote sandbox configurations."""
    async with session() as s:
        result = await s.execute(
            select(Setting).where(Setting.key.startswith(REMOTE_SANDBOX_KEY_PREFIX))
        )
        return [_parse_config(setting) for setting in result.scalars().all()]


@router.get("/sandboxes/{sandbox_id}")
async def get_sandbox(sandbox_id: str) -> RemoteSandboxResponse:
    """Get a single remote sandbox configuration."""
    async with session() as s:
        setting = await s.get(Setting, _setting_key(sandbox_id))
        if not setting:
            raise HTTPException(status_code=404, detail="Remote sandbox not found")
        return _parse_config(setting)


@router.post("/sandboxes")
async def create_sandbox(body: RemoteSandboxConfig) -> dict:
    """Create a new remote sandbox configuration."""
    sandbox_id = str(uuid.uuid4())
    data = _config_to_dict(body)
    async with session() as s:
        await upsert_setting(s, _setting_key(sandbox_id), json.dumps(data), False)
        await s.commit()
    return {"ok": True, "sandbox_id": sandbox_id}


@router.put("/sandboxes/{sandbox_id}")
async def update_sandbox(sandbox_id: str, body: RemoteSandboxConfig) -> dict:
    """Update a remote sandbox configuration."""
    async with session() as s:
        existing = await s.get(Setting, _setting_key(sandbox_id))
        if not existing:
            raise HTTPException(status_code=404, detail="Remote sandbox not found")
        data = _config_to_dict(body)
        await upsert_setting(s, _setting_key(sandbox_id), json.dumps(data), False)
        await s.commit()
    return {"ok": True, "sandbox_id": sandbox_id}


@router.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str) -> dict:
    """Delete a remote sandbox configuration. Fails if active runs exist."""
    async with session() as s:
        setting = await s.get(Setting, _setting_key(sandbox_id))
        if not setting:
            raise HTTPException(status_code=404, detail="Remote sandbox not found")

        active_count = (
            await s.execute(
                select(func.count())
                .select_from(Run)
                .where(Run.sandbox_id == sandbox_id)
                .where(Run.status.in_(ACTIVE_RUN_STATUSES))
            )
        ).scalar_one()
        if active_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete: {active_count} active run(s) use this sandbox",
            )

        await s.delete(setting)
        await s.commit()
    return {"ok": True, "sandbox_id": sandbox_id}


@router.get("/sandboxes/{sandbox_id}/last-start-cmd")
async def get_last_start_cmd(
    sandbox_id: str,
    repo: str = Query(...),
) -> dict:
    """Get the last-used start command for a repo+sandbox combination."""
    key = f"{LAST_START_CMD_KEY_PREFIX}{repo}:{sandbox_id}"
    async with session() as s:
        setting = await s.get(Setting, key)
        if not setting:
            return {"start_cmd": None}
        return {"start_cmd": setting.value}


@router.get("/repos/{repo:path}/remote-mounts/{sandbox_id}")
async def get_remote_mounts(repo: str, sandbox_id: str) -> dict:
    """Get host mounts for a remote sandbox + repo combination."""
    key = f"{REMOTE_MOUNTS_KEY_PREFIX}{repo}:{sandbox_id}"
    async with session() as s:
        setting = await s.get(Setting, key)
        if not setting:
            return {"mounts": []}
        return {"mounts": json.loads(setting.value)}


@router.put("/repos/{repo:path}/remote-mounts/{sandbox_id}")
async def save_remote_mounts(
    repo: str,
    sandbox_id: str,
    body: dict,
) -> dict:
    """Save host mounts for a remote sandbox + repo combination."""
    mounts: list[dict] = body.get("mounts", [])
    key = f"{REMOTE_MOUNTS_KEY_PREFIX}{repo}:{sandbox_id}"
    async with session() as s:
        if mounts:
            await upsert_setting(s, key, json.dumps(mounts), False)
        else:
            existing = await s.get(Setting, key)
            if existing:
                await s.delete(existing)
        await s.commit()
    return {"ok": True}
