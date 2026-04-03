"""Dashboard API endpoints — settings, repos, and token pool."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func

from backend import auth, crypto
from backend.constants import (
    MASK_PREFIX_CLAUDE_TOKEN,
    MASK_PREFIX_DEFAULT,
    MASTER_KEY_PATH,
    SECRET_KEYS,
)
from backend.models import (
    AddTokenRequest,
    SetActiveRepoRequest,
    UpdateSettingsRequest,
)
from backend.utils import (
    add_token_to_pool,
    ensure_repo_in_list,
    get_repo_list,
    list_pool_tokens,
    remove_token_from_pool,
    save_repo_list,
    session,
    upsert_setting,
)
from db.models import Run, Setting

log = logging.getLogger("dashboard.settings")

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])


@router.get("/settings/status")
async def settings_status() -> dict:
    """Check which credentials are configured."""
    async with session() as s:
        has: dict[str, bool] = {}
        has["has_claude_token"] = (
            (await s.get(Setting, "claude_token")) is not None
            or (await s.get(Setting, "claude_tokens")) is not None
        )
        for key in ("git_token", "github_repo"):
            has[f"has_{key}"] = (await s.get(Setting, key)) is not None
        has["configured"] = all(has.values())
        return has


async def _decrypt_setting(setting: Setting) -> str:
    """Decrypt and mask an encrypted setting value."""
    plain = crypto.decrypt(setting.value, MASTER_KEY_PATH)
    prefix = MASK_PREFIX_CLAUDE_TOKEN if setting.key == "claude_token" else MASK_PREFIX_DEFAULT
    return crypto.mask(plain, prefix_len=prefix)


@router.get("/settings")
async def get_settings() -> dict:
    """Get all settings with secrets masked."""
    async with session() as s:
        result = await s.execute(select(Setting))
        settings: dict[str, str] = {}
        for setting in result.scalars().all():
            if setting.encrypted:
                try:
                    settings[setting.key] = await _decrypt_setting(setting)
                except Exception as e:
                    log.error("Failed to decrypt setting '%s': %s", setting.key, e)
                    settings[setting.key] = "****"
            else:
                settings[setting.key] = setting.value
        return settings


@router.put("/settings")
async def update_settings(body: UpdateSettingsRequest) -> dict:
    """Create or update settings. Secrets are encrypted before storage."""
    updates = body.model_dump(exclude_none=True)
    async with session() as s:
        for key, value in updates.items():
            is_secret = key in SECRET_KEYS
            stored_val = crypto.encrypt(value, MASTER_KEY_PATH) if is_secret else value
            await upsert_setting(s, key, stored_val, is_secret)
        if "github_repo" in updates and updates["github_repo"]:
            await ensure_repo_in_list(s, updates["github_repo"])
        await s.commit()
    auth.clear_cache()
    return {"ok": True, "updated": list(updates.keys())}


@router.get("/repos")
async def list_repos() -> list:
    """List all configured repos with run counts."""
    async with session() as s:
        repos = await get_repo_list(s)

        active = await s.get(Setting, "github_repo")
        if active and active.value and active.value not in repos:
            await ensure_repo_in_list(s, active.value)
            repos.append(active.value)
            await s.commit()

        result = []
        for repo in repos:
            count = (await s.execute(
                select(func.count()).select_from(Run).where(Run.github_repo == repo)
            )).scalar_one()
            result.append({"repo": repo, "run_count": count})
        return result


@router.put("/repos/active")
async def set_active_repo(body: SetActiveRepoRequest) -> dict:
    """Set the active repo."""
    async with session() as s:
        await upsert_setting(s, "github_repo", body.repo, False)
        await ensure_repo_in_list(s, body.repo)
        await s.commit()
    return {"ok": True, "active_repo": body.repo}


@router.delete("/repos/{repo_slug:path}")
async def remove_repo(repo_slug: str) -> dict:
    """Remove a repo from the list (does not delete runs)."""
    if not re.match(r'^[\w\-\.]+/[\w\-\.]+$', repo_slug):
        raise HTTPException(status_code=400, detail="Invalid repo slug format")
    async with session() as s:
        repos = [r for r in await get_repo_list(s) if r != repo_slug]
        await save_repo_list(s, repos)
        await s.commit()
    return {"ok": True, "remaining": repos}


@router.get("/tokens")
async def get_tokens() -> list:
    """List all Claude tokens in the pool (masked)."""
    return await list_pool_tokens()


@router.post("/tokens")
async def add_token(body: AddTokenRequest) -> dict:
    """Add a Claude token to the pool."""
    try:
        return await add_token_to_pool(body.token.strip())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/tokens/{index}")
async def delete_token(index: int) -> dict:
    """Remove a token from the pool by index."""
    try:
        return await remove_token_from_pool(index)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
