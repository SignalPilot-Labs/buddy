"""Pydantic request models and path validators for the dashboard API."""

from fastapi import Path
from pydantic import BaseModel, Field

from db.constants import DEFAULT_EFFORT, DEFAULT_MODEL, VALID_EFFORTS_PATTERN, VALID_MODELS_PATTERN


RunId = Path(min_length=36, max_length=36, pattern=r"^[0-9a-f\-]{36}$")


class ControlSignalRequest(BaseModel):
    """Request body for control signal endpoints."""

    payload: str | None = None


class StopRunRequest(BaseModel):
    """Request body for the stop endpoint."""

    payload: str | None = None
    skip_pr: bool


class StartRunRequest(BaseModel):
    """Request body for starting a new run."""

    prompt: str | None = None
    max_budget_usd: float = Field(default=0, ge=0, description="Max spend in USD. 0 = unlimited.")
    duration_minutes: float = Field(default=0, ge=0, description="Session duration in minutes. 0 = unlimited.")
    base_branch: str = Field(default="main", min_length=1, max_length=256, description="Branch to base the work on.")
    model: str = Field(default=DEFAULT_MODEL, pattern=VALID_MODELS_PATTERN, description="Claude model to use.")
    effort: str = Field(default=DEFAULT_EFFORT, pattern=VALID_EFFORTS_PATTERN, description="Thinking effort level.")
    repo: str | None = Field(None, description="Active repo slug for per-repo env vars lookup.")


class UpdateSettingsRequest(BaseModel):
    """Request body for updating settings."""

    git_token: str | None = Field(None, min_length=1, max_length=4096)
    github_repo: str | None = Field(None, min_length=1, max_length=256, pattern=r"^[\w\-\.]+/[\w\-\.]+$")
    max_budget_usd: str | None = Field(None, min_length=1, max_length=20)
    dashboard_api_key: str | None = Field(None, min_length=20, max_length=256)
    model: str | None = Field(None, pattern=VALID_MODELS_PATTERN, description="Default Claude model.")


class SetActiveRepoRequest(BaseModel):
    """Request body for setting active repo."""

    repo: str = Field(min_length=1, max_length=256, pattern=r"^[\w\-\.]+/[\w\-\.]+$")


class ResumeRunRequest(BaseModel):
    """Request body for resuming a previous run."""

    run_id: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-f\-]{36}$")
    max_budget_usd: float = Field(default=0, ge=0, description="Max spend in USD. 0 = unlimited.")
    model: str | None = Field(None, pattern=VALID_MODELS_PATTERN, description="Override model for the resumed run. Defaults to the original run's model.")


class AddTokenRequest(BaseModel):
    """Request body for adding a Claude token to the pool."""

    token: str = Field(min_length=1, max_length=4096)
