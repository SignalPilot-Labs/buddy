"""Dashboard utility functions — agent HTTP proxy, ORM helpers, DB access helpers."""

import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend import crypto
from backend.constants import AGENT_API_URL, AGENT_TIMEOUT_SHORT, MASTER_KEY_PATH, SECRET_KEYS
from db.connection import get_session_factory
from db.models import ControlSignal, Run, Setting

_AGENT_INTERNAL_SECRET = os.environ.get("AGENT_INTERNAL_SECRET", "")

log = logging.getLogger("backend.utils")


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

@asynccontextmanager
async def session() -> AsyncGenerator[AsyncSession]:
    """Yield an async DB session."""
    async with get_session_factory()() as s:
        yield s


# ---------------------------------------------------------------------------
# ORM helpers
# ---------------------------------------------------------------------------

def model_to_dict(obj) -> dict:
    """Convert an ORM model instance to a JSON-safe dict."""
    d = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
    for key, val in d.items():
        if hasattr(val, "isoformat"):
            d[key] = val.isoformat()
    return d


# ---------------------------------------------------------------------------
# Settings data access
# ---------------------------------------------------------------------------

async def upsert_setting(s: AsyncSession, key: str, value: str, encrypted: bool) -> None:
    """Upsert a single setting."""
    await s.execute(
        pg_insert(Setting)
        .values(key=key, value=value, encrypted=encrypted)
        .on_conflict_do_update(index_elements=["key"], set_={"value": value, "encrypted": encrypted})
    )


async def get_repo_list(s: AsyncSession) -> list[str]:
    """Read the repos JSON array from settings."""
    setting = await s.get(Setting, "repos")
    if not setting:
        return []
    try:
        return json.loads(setting.value)
    except (json.JSONDecodeError, TypeError):
        return []


async def save_repo_list(s: AsyncSession, repos: list[str]) -> None:
    """Write the repos JSON array to settings."""
    await upsert_setting(s, "repos", json.dumps(repos), False)


async def ensure_repo_in_list(s: AsyncSession, repo: str) -> None:
    """Add repo to the list if not already present."""
    repos = await get_repo_list(s)
    if repo not in repos:
        repos.append(repo)
        await save_repo_list(s, repos)


async def read_credentials() -> dict:
    """Read and decrypt stored credentials."""
    creds = {}
    async with session() as s:
        for key in ("claude_token", "git_token", "github_repo"):
            setting = await s.get(Setting, key)
            if not setting:
                continue
            if setting.encrypted:
                try:
                    creds[key] = crypto.decrypt(setting.value, MASTER_KEY_PATH)
                except Exception as e:
                    log.error("Failed to decrypt %s: %s", key, e)
            else:
                creds[key] = setting.value
    return creds


# ---------------------------------------------------------------------------
# Control signals
# ---------------------------------------------------------------------------

async def send_control_signal(
    run_id: str,
    signal: str,
    allowed_statuses: set[str],
    payload: str | None,
) -> dict:
    """Validate run status, persist signal, then forward to agent."""
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.status not in allowed_statuses:
            raise HTTPException(status_code=409, detail=f"Cannot {signal} run with status '{run.status}'")
        s.add(ControlSignal(run_id=run_id, signal=signal, payload=payload))
        await s.commit()
    await send_agent_signal(signal, payload)
    result = {"ok": True, "signal": signal}
    if payload:
        result["payload_length"] = len(payload)
    return result


# ---------------------------------------------------------------------------
# Agent HTTP proxy
# ---------------------------------------------------------------------------

_SIGNAL_ENDPOINT_MAP = {
    "resume": "resume_signal",
    "pause": "pause",
    "inject": "inject",
    "stop": "stop",
    "unlock": "unlock",
}


async def agent_request(
    method: str,
    path: str,
    timeout: int,
    json_body: dict | None,
    params: dict | None,
    fallback: Any,
) -> Any:
    """Make an HTTP request to the agent container.

    On success returns the JSON response. On connection failure:
    - If fallback is provided, returns it silently.
    - Otherwise raises HTTP 502.
    Preserves 409 conflict errors from the agent.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {"X-Internal-Secret": _AGENT_INTERNAL_SECRET} if _AGENT_INTERNAL_SECRET else {}
            res = await client.request(
                method, f"{AGENT_API_URL}{path}", json=json_body, params=params, headers=headers,
            )
            if res.status_code == 409:
                raise HTTPException(status_code=409, detail=res.json().get("detail", "Conflict"))
            if res.status_code >= 400:
                log.warning("Agent returned %d for %s %s", res.status_code, method, path)
                try:
                    detail = res.json().get("detail", f"Agent error {res.status_code}")
                except Exception:
                    detail = f"Agent error {res.status_code}"
                raise HTTPException(status_code=502, detail=detail)
            return res.json()
    except HTTPException:
        raise
    except Exception as e:
        if fallback is not None:
            return fallback
        log.error("Agent request failed: %s %s — %s", method, path, e)
        raise HTTPException(status_code=502, detail="Agent service unavailable")


async def send_agent_signal(signal: str, payload: str | None) -> None:
    """Forward a control signal to the agent container via HTTP."""
    endpoint = _SIGNAL_ENDPOINT_MAP.get(signal, signal)
    body = {"payload": payload} if payload else {}
    await agent_request("POST", f"/{endpoint}", AGENT_TIMEOUT_SHORT, body, None, None)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

async def autofill_settings(master_key_path: str) -> None:
    """Import env vars into settings DB if settings are empty (first-boot autofill)."""
    async with session() as s:
        result = await s.execute(select(func.count()).select_from(Setting))
        if result.scalar_one() > 0:
            return

        env_mappings = {
            "claude_token": "CLAUDE_CODE_OAUTH_TOKEN",
            "git_token": "GIT_TOKEN",
            "github_repo": "GITHUB_REPO",
            "max_budget_usd": "MAX_BUDGET_USD",
        }

        for key, env_var in env_mappings.items():
            val = os.environ.get(env_var)
            if not val:
                continue
            is_secret = key in SECRET_KEYS
            stored_val = crypto.encrypt(val, master_key_path) if is_secret else val
            await upsert_setting(s, key, stored_val, is_secret)

        await s.commit()
