"""Dashboard utility functions — agent HTTP proxy, ORM helpers, DB access helpers."""

import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend import crypto
from backend.constants import AGENT_API_URL, MASTER_KEY_PATH, SECRET_KEYS
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
        if isinstance(val, datetime):
            d[key] = val.isoformat()
    return d


# ---------------------------------------------------------------------------
# Control signals
# ---------------------------------------------------------------------------

async def send_control_signal(
    run_id: str, signal: str, valid_statuses: set[str], payload: str | None,
) -> dict:
    """Insert a control signal for a run after validating its status."""
    async with session() as s:
        run = await s.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.status not in valid_statuses:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot send '{signal}' to run with status '{run.status}'",
            )
        s.add(ControlSignal(run_id=run_id, signal=signal, payload=payload))
        await s.commit()
    return {"ok": True, "signal": signal, "run_id": run_id}


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
    """Read and decrypt stored credentials. Picks next Claude token round-robin."""
    creds: dict[str, str] = {}
    async with session() as s:
        for key in ("git_token", "github_repo"):
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

        token = await _pick_next_claude_token(s)
        if token:
            creds["claude_token"] = token

    return creds


async def _pick_next_claude_token(s: AsyncSession) -> str | None:
    """Pick the next Claude token round-robin from the token pool.

    Tokens are stored as an encrypted JSON array in settings key 'claude_tokens'.
    The current index is tracked in 'claude_token_index'.
    Falls back to the single 'claude_token' setting for backward compatibility.
    """
    pool = await s.get(Setting, "claude_tokens")
    if pool:
        try:
            tokens = json.loads(crypto.decrypt(pool.value, MASTER_KEY_PATH))
            if tokens:
                idx_row = await s.get(Setting, "claude_token_index")
                idx = int(idx_row.value) if idx_row else 0
                idx = idx % len(tokens)
                picked = tokens[idx]
                await upsert_setting(s, "claude_token_index", str((idx + 1) % len(tokens)), False)
                # Commit here because read_credentials() owns the session —
                # index must persist even if the caller doesn't write anything.
                await s.commit()
                return picked
        except (json.JSONDecodeError, TypeError, IndexError, ValueError) as e:
            log.warning("Failed to read claude_tokens pool: %s", e)

    # Fallback: single token
    single = await s.get(Setting, "claude_token")
    if not single:
        return None
    try:
        return crypto.decrypt(single.value, MASTER_KEY_PATH) if single.encrypted else single.value
    except Exception as e:
        log.error("Failed to decrypt claude_token: %s", e)
        return None


# ---------------------------------------------------------------------------
# Token pool CRUD
# ---------------------------------------------------------------------------

async def _read_token_pool(s: AsyncSession) -> list[str]:
    """Read the decrypted token pool. Returns empty list if not set."""
    pool = await s.get(Setting, "claude_tokens")
    if not pool:
        return []
    try:
        return json.loads(crypto.decrypt(pool.value, MASTER_KEY_PATH))
    except (json.JSONDecodeError, TypeError, Exception):
        return []


async def _write_token_pool(s: AsyncSession, tokens: list[str]) -> None:
    """Encrypt and write the token pool."""
    encrypted = crypto.encrypt(json.dumps(tokens), MASTER_KEY_PATH)
    await upsert_setting(s, "claude_tokens", encrypted, True)


async def add_token_to_pool(raw_token: str) -> dict:
    """Add a Claude token to the pool. Rejects duplicates."""
    async with session() as s:
        tokens = await _read_token_pool(s)
        if raw_token in tokens:
            raise ValueError("This token is already in the pool")
        tokens.append(raw_token)
        await _write_token_pool(s, tokens)
        await s.commit()
    return {"ok": True, "count": len(tokens)}


async def list_pool_tokens() -> list[dict]:
    """List all tokens in the pool (masked)."""
    async with session() as s:
        tokens = await _read_token_pool(s)
        idx_row = await s.get(Setting, "claude_token_index")
        current_idx = int(idx_row.value) if idx_row else 0
    if not tokens:
        return []
    active_idx = current_idx % len(tokens)
    return [
        {"index": i, "masked": crypto.mask(t, prefix_len=8), "active": i == active_idx}
        for i, t in enumerate(tokens)
    ]


async def remove_token_from_pool(index: int) -> dict:
    """Remove a token by index. Adjusts round-robin index to avoid skipping."""
    async with session() as s:
        tokens = await _read_token_pool(s)
        if index < 0 or index >= len(tokens):
            raise ValueError(f"Index {index} out of range (pool has {len(tokens)} tokens)")
        tokens.pop(index)
        await _write_token_pool(s, tokens)
        # Adjust round-robin index
        idx_row = await s.get(Setting, "claude_token_index")
        if idx_row and tokens:
            current = int(idx_row.value)
            if index < current:
                await upsert_setting(s, "claude_token_index", str(current - 1), False)
            elif current >= len(tokens):
                await upsert_setting(s, "claude_token_index", str(0), False)
        elif idx_row and not tokens:
            await upsert_setting(s, "claude_token_index", str(0), False)
        await s.commit()
    return {"ok": True, "count": len(tokens)}


# ---------------------------------------------------------------------------
# Agent HTTP proxy
# ---------------------------------------------------------------------------


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
            if res.status_code >= 400:
                log.warning("Agent returned %d for %s %s", res.status_code, method, path)
                try:
                    detail = res.json().get("detail", f"Agent error {res.status_code}")
                except Exception:
                    detail = f"Agent error {res.status_code}"
                # Preserve client-meaningful status codes; wrap others as 502
                if res.status_code in (404, 409, 422, 429):
                    raise HTTPException(status_code=res.status_code, detail=detail)
                raise HTTPException(status_code=502, detail=detail)
            return res.json()
    except HTTPException:
        raise
    except Exception as e:
        if fallback is not None:
            return fallback
        log.error("Agent request failed: %s %s — %s", method, path, e)
        raise HTTPException(status_code=502, detail="Agent service unavailable")


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


