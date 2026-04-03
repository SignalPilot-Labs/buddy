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
    max_budget_usd: float = Field(description="Max spend in USD. 0 = unlimited.")
    duration_minutes: float = Field(description="Session duration in minutes. 0 = unlimited.")
    base_branch: str = Field(min_length=1, max_length=256, description="Branch to base the work on.")


class ResumeRunRequest(BaseModel):
    """Request body for resuming a run."""

    run_id: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-f\-]{36}$")
    max_budget_usd: float = Field(description="Max spend in USD. 0 = unlimited.")


class UpdateSettingsRequest(BaseModel):
    """Request body for updating settings."""

    claude_token: str | None = Field(None, min_length=1, max_length=4096)
    git_token: str | None = Field(None, min_length=1, max_length=4096)
    github_repo: str | None = Field(None, min_length=1, max_length=256, pattern=r"^[\w\-\.]+/[\w\-\.]+$")
    max_budget_usd: str | None = Field(None, min_length=1, max_length=20)
    dashboard_api_key: str | None = Field(None, min_length=20, max_length=256)


class SetActiveRepoRequest(BaseModel):
    """Request body for setting active repo."""

    repo: str = Field(min_length=1, max_length=256, pattern=r"^[\w\-\.]+/[\w\-\.]+$")
