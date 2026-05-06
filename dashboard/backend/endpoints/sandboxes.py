"""Dashboard API endpoints — remote sandbox CRUD."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, func

from backend import auth
from backend.endpoints.settings import validate_repo_slug
from backend.utils import AGENT_TIMEOUT_SHORT, agent_request, session, upsert_setting
from db.constants import (
    ACTIVE_RUN_STATUSES,
    HEARTBEAT_TIMEOUT_MAX,
    HEARTBEAT_TIMEOUT_MIN,
    LAST_START_CMD_KEY_PREFIX,
    MAX_REMOTE_MOUNTS,
    QUEUE_TIMEOUT_MAX,
    QUEUE_TIMEOUT_MIN,
    REMOTE_MOUNTS_KEY_PREFIX,
    REMOTE_SANDBOX_KEY_PREFIX,
    SANDBOX_NAME_MAX_LEN,
    SANDBOX_NAME_MIN_LEN,
    SSH_TARGET_MAX_LEN,
    SSH_TARGET_MIN_LEN,
    SSH_TARGET_RE,
    START_CMD_MAX_LEN,
    START_CMD_MIN_LEN,
    VALID_SANDBOX_TYPES,
    WORK_DIR_RE,
    validate_remote_mount_path,
)
from db.models import Run, Setting

log = logging.getLogger("dashboard.sandboxes")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

SANDBOX_TYPE_PATTERN: str = f"^({'|'.join(VALID_SANDBOX_TYPES)})$"


class RemoteSandboxConfig(BaseModel):
    """Request body for creating/updating a remote sandbox config."""

    name: str = Field(min_length=SANDBOX_NAME_MIN_LEN, max_length=SANDBOX_NAME_MAX_LEN)
    ssh_target: str = Field(min_length=SSH_TARGET_MIN_LEN, max_length=SSH_TARGET_MAX_LEN)
    type: str = Field(pattern=SANDBOX_TYPE_PATTERN)
    default_start_cmd: str = Field(min_length=START_CMD_MIN_LEN, max_length=START_CMD_MAX_LEN)
    queue_timeout: int = Field(ge=QUEUE_TIMEOUT_MIN, le=QUEUE_TIMEOUT_MAX)
    heartbeat_timeout: int = Field(ge=HEARTBEAT_TIMEOUT_MIN, le=HEARTBEAT_TIMEOUT_MAX)
    work_dir: str = Field(max_length=4096)

    @field_validator("ssh_target")
    @classmethod
    def validate_ssh_target(cls, v: str) -> str:
        """Reject shell metacharacters in SSH targets."""
        if not SSH_TARGET_RE.fullmatch(v):
            raise ValueError(
                "SSH target contains unsafe characters — "
                "only alphanumeric, @, ., _, :, /, - allowed"
            )
        return v

    @field_validator("work_dir")
    @classmethod
    def validate_work_dir(cls, v: str) -> str:
        """Reject shell metacharacters in work directory paths."""
        if v and not WORK_DIR_RE.fullmatch(v):
            raise ValueError(
                "Work directory contains unsafe characters — "
                "only alphanumeric, ~, ., _, /, - allowed"
            )
        return v

    @model_validator(mode="after")
    def require_work_dir_for_slurm(self) -> "RemoteSandboxConfig":
        """Slurm sandboxes require a work directory for overlay storage."""
        if self.type == "slurm" and not self.work_dir.strip():
            raise ValueError("Work directory is required for Slurm sandboxes")
        return self


class RemoteSandboxResponse(BaseModel):
    """Response for a single remote sandbox config."""

    id: str
    name: str
    ssh_target: str
    type: str
    default_start_cmd: str
    queue_timeout: int
    heartbeat_timeout: int
    work_dir: str


class RemoteMountEntry(BaseModel):
    """A single remote mount entry."""

    host_path: str = Field(min_length=1, max_length=4096)
    container_path: str = Field(min_length=1, max_length=4096)
    mode: str = Field(pattern=r"^(ro|rw)$")

    @field_validator("host_path", "container_path")
    @classmethod
    def validate_mount_path(cls, v: str) -> str:
        """Validate mount paths using the shared remote mount validator."""
        error = validate_remote_mount_path(v)
        if error:
            raise ValueError(error)
        return v


class SaveRemoteMountsRequest(BaseModel):
    """Request body for saving remote mounts."""

    mounts: list[RemoteMountEntry] = Field(default_factory=list, max_length=MAX_REMOTE_MOUNTS)


def _setting_key(sandbox_id: str) -> str:
    """Build the settings table key for a remote sandbox config."""
    return f"{REMOTE_SANDBOX_KEY_PREFIX}{sandbox_id}"


def _parse_config(setting: Setting) -> RemoteSandboxResponse:
    """Parse a Setting row into a RemoteSandboxResponse."""
    sandbox_id = setting.key.removeprefix(REMOTE_SANDBOX_KEY_PREFIX)
    raw: dict[str, str | int] = json.loads(setting.value)
    required_keys = ("name", "ssh_target", "type", "default_start_cmd", "queue_timeout", "heartbeat_timeout", "work_dir")
    missing = [k for k in required_keys if k not in raw]
    if missing:
        raise ValueError(f"Sandbox {sandbox_id} config missing required fields: {', '.join(missing)}. Re-save the sandbox in Settings to fix.")
    return RemoteSandboxResponse(
        id=sandbox_id,
        name=str(raw["name"]),
        ssh_target=str(raw["ssh_target"]),
        type=str(raw["type"]),
        default_start_cmd=str(raw["default_start_cmd"]),
        queue_timeout=int(raw["queue_timeout"]),
        heartbeat_timeout=int(raw["heartbeat_timeout"]),
        work_dir=str(raw["work_dir"]),
    )


def _config_to_dict(body: RemoteSandboxConfig) -> dict[str, str | int]:
    """Convert a RemoteSandboxConfig to a serializable dict."""
    return {
        "name": body.name,
        "ssh_target": body.ssh_target,
        "type": body.type,
        "default_start_cmd": body.default_start_cmd,
        "queue_timeout": body.queue_timeout,
        "heartbeat_timeout": body.heartbeat_timeout,
        "work_dir": body.work_dir,
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


@router.post("/sandboxes", status_code=201)
async def create_sandbox(body: RemoteSandboxConfig) -> dict[str, str | bool]:
    """Create a new remote sandbox configuration."""
    sandbox_id = str(uuid.uuid4())
    data = _config_to_dict(body)
    async with session() as s:
        await upsert_setting(s, _setting_key(sandbox_id), json.dumps(data), False)
        await s.commit()
    return {"ok": True, "sandbox_id": sandbox_id}


@router.put("/sandboxes/{sandbox_id}")
async def update_sandbox(sandbox_id: str, body: RemoteSandboxConfig) -> dict[str, str | bool]:
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
async def delete_sandbox(sandbox_id: str) -> dict[str, str | bool | int]:
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


@router.post("/sandboxes/{sandbox_id}/test")
async def test_sandbox(sandbox_id: str) -> dict:
    """Test SSH connection and image availability via agent → connector → SSH."""
    return await agent_request(
        "POST", f"/test-sandbox/{sandbox_id}", AGENT_TIMEOUT_SHORT, None, None, None,
        extra_headers=None,
    )


@router.get("/sandboxes/{sandbox_id}/last-start-cmd")
async def get_last_start_cmd(
    sandbox_id: str,
    repo: str = Query(...),
) -> dict[str, str | None]:
    """Get the last-used start command for a repo+sandbox combination."""
    repo = validate_repo_slug(repo)
    key = f"{LAST_START_CMD_KEY_PREFIX}{repo}:{sandbox_id}"
    async with session() as s:
        setting = await s.get(Setting, key)
        if not setting:
            return {"start_cmd": None}
        return {"start_cmd": setting.value}


@router.get("/repos/{repo:path}/remote-mounts/{sandbox_id}")
async def get_remote_mounts(repo: str, sandbox_id: str) -> dict[str, list[dict[str, str]]]:
    """Get host mounts for a remote sandbox + repo combination."""
    repo = validate_repo_slug(repo)
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
    body: SaveRemoteMountsRequest,
) -> dict[str, bool]:
    """Save host mounts for a remote sandbox + repo combination."""
    repo = validate_repo_slug(repo)
    key = f"{REMOTE_MOUNTS_KEY_PREFIX}{repo}:{sandbox_id}"
    async with session() as s:
        if body.mounts:
            mounts_data = [m.model_dump() for m in body.mounts]
            await upsert_setting(s, key, json.dumps(mounts_data), False)
        else:
            existing = await s.get(Setting, key)
            if existing:
                await s.delete(existing)
        await s.commit()
    return {"ok": True}
