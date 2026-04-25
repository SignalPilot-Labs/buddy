"""Pydantic request models and path validators for the dashboard API."""

from fastapi import Path
from pydantic import BaseModel, Field, field_validator

from db.constants import DEFAULT_EFFORT, DEFAULT_MODEL, GITHUB_REPO_MAX_LEN, GITHUB_REPO_PATTERN, MAX_HOST_MOUNTS, PROMPT_MAX_LEN, VALID_EFFORTS_PATTERN, VALID_MODELS_PATTERN, VALID_PRESET_PATTERN


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
    preset: str | None = Field(None, pattern=VALID_PRESET_PATTERN, description="Starter preset key. Mutually exclusive with prompt.")
    max_budget_usd: float = Field(default=0, ge=0, description="Max spend in USD. 0 = unlimited.")
    duration_minutes: float = Field(default=0, ge=0, description="Session duration in minutes. 0 = unlimited.")
    base_branch: str = Field(default="main", min_length=1, max_length=256, description="Branch to base the work on.")
    model: str = Field(default=DEFAULT_MODEL, pattern=VALID_MODELS_PATTERN, description="Claude model to use.")
    effort: str = Field(default=DEFAULT_EFFORT, pattern=VALID_EFFORTS_PATTERN, description="Thinking effort level.")
    repo: str | None = Field(None, description="Active repo slug for per-repo env vars lookup.")

    @field_validator("prompt")
    @classmethod
    def prompt_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > PROMPT_MAX_LEN:
            raise ValueError(f"prompt must be under {PROMPT_MAX_LEN} characters")
        return v


class UpdateSettingsRequest(BaseModel):
    """Request body for updating settings."""

    git_token: str | None = Field(None, min_length=1, max_length=4096)
    github_repo: str | None = Field(None, min_length=1, max_length=GITHUB_REPO_MAX_LEN, pattern=GITHUB_REPO_PATTERN)
    max_budget_usd: str | None = Field(None, min_length=1, max_length=20)
    dashboard_api_key: str | None = Field(None, min_length=20, max_length=256)
    model: str | None = Field(None, pattern=VALID_MODELS_PATTERN, description="Default Claude model.")


class SetActiveRepoRequest(BaseModel):
    """Request body for setting active repo."""

    repo: str = Field(min_length=1, max_length=GITHUB_REPO_MAX_LEN, pattern=GITHUB_REPO_PATTERN)


class ResumeRunRequest(BaseModel):
    """Request body for resuming a previous run."""

    run_id: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-f\-]{36}$")
    max_budget_usd: float = Field(default=0, ge=0, description="Max spend in USD. 0 = unlimited.")
    model: str | None = Field(None, pattern=VALID_MODELS_PATTERN, description="Override model for the resumed run. Defaults to the original run's model.")


class HostMountEntry(BaseModel):
    """A single host directory mount."""

    host_path: str = Field(min_length=1, max_length=4096)
    container_path: str = Field(min_length=1, max_length=4096)
    mode: str = Field(pattern=r"^(ro|rw)$")


class SaveMountsRequest(BaseModel):
    """Request body for saving per-repo host mounts."""

    mounts: list[HostMountEntry] = Field(default_factory=list, max_length=MAX_HOST_MOUNTS)


class AddTokenRequest(BaseModel):
    """Request body for adding a Claude token to the pool."""

    token: str = Field(min_length=1, max_length=4096)
