"""Pydantic request models and path validators for the dashboard API."""

from fastapi import Path
from pydantic import BaseModel, Field


RunId = Path(min_length=36, max_length=36, pattern=r"^[0-9a-f\-]{36}$")


class ControlSignalRequest(BaseModel):
    """Request body for control signal endpoints."""

    payload: str | None = None


class StartRunRequest(BaseModel):
    """Request body for starting a new run."""

    prompt: str | None = None
    max_budget_usd: float = Field(default=0, ge=0, description="Max spend in USD. 0 = unlimited.")
    duration_minutes: float = Field(default=0, ge=0, description="Session duration in minutes. 0 = unlimited.")
    base_branch: str = Field(default="main", min_length=1, max_length=256, description="Branch to base the work on.")
    extended_context: bool = Field(default=False, description="Enable 1M extended context.")


class UpdateSettingsRequest(BaseModel):
    """Request body for updating settings."""

    claude_token: str | None = Field(None, min_length=1, max_length=4096)
    git_token: str | None = Field(None, min_length=1, max_length=4096)
    github_repo: str | None = Field(None, min_length=1, max_length=256, pattern=r"^[\w\-\.]+/[\w\-\.]+$")
    max_budget_usd: str | None = Field(None, min_length=1, max_length=20)
    dashboard_api_key: str | None = Field(None, min_length=20, max_length=256)
    repo_env_vars: dict[str, str] | None = Field(None)


class SetActiveRepoRequest(BaseModel):
    """Request body for setting active repo."""

    repo: str = Field(min_length=1, max_length=256, pattern=r"^[\w\-\.]+/[\w\-\.]+$")


class ResumeRunRequest(BaseModel):
    """Request body for resuming a previous run."""

    run_id: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-f\-]{36}$")
    max_budget_usd: float = Field(default=0, ge=0, description="Max spend in USD. 0 = unlimited.")


class AddTokenRequest(BaseModel):
    """Request body for adding a Claude token to the pool."""

    token: str = Field(min_length=1, max_length=4096)
