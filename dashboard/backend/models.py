"""Pydantic request models and path validators for the dashboard API."""

from fastapi import Path
from pydantic import BaseModel, Field, field_validator

from db.constants import DEFAULT_EFFORT, DEFAULT_MODEL, ENV_VAR_KEY_RE, ENV_VAR_MAX_KEY_LEN, ENV_VAR_MAX_VALUE_LEN, GITHUB_REPO_MAX_LEN, GITHUB_REPO_PATTERN, MAX_ENV_VARS, MAX_HOST_MOUNTS, MAX_MCP_SERVERS, VALID_EFFORTS_PATTERN, VALID_MODELS_PATTERN, VALID_PRESET_PATTERN, validate_prompt_length


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
    sandbox_id: str | None = Field(None, description="UUID of remote sandbox config. None for local Docker.")
    start_cmd: str | None = Field(None, max_length=65536, description="Start command for remote sandbox. None for local Docker.")

    @field_validator("prompt")
    @classmethod
    def prompt_max_length(cls, v: str | None) -> str | None:
        """Validate prompt length."""
        return validate_prompt_length(v)


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


class SaveMcpServersRequest(BaseModel):
    """Request body for saving per-repo MCP server configurations."""

    servers: dict[str, dict] = Field(default_factory=dict)

    @field_validator("servers")
    @classmethod
    def servers_max_count(cls, v: dict[str, dict]) -> dict[str, dict]:
        """Validate that the number of servers does not exceed MAX_MCP_SERVERS."""
        if len(v) > MAX_MCP_SERVERS:
            raise ValueError(f"Cannot configure more than {MAX_MCP_SERVERS} MCP servers")
        return v


class SaveRepoEnvRequest(BaseModel):
    """Request body for saving per-repo environment variables."""

    env_vars: dict[str, str]

    @field_validator("env_vars")
    @classmethod
    def validate_env_vars(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate count, key format, and value length for all env vars."""
        if len(v) > MAX_ENV_VARS:
            raise ValueError(f"Cannot store more than {MAX_ENV_VARS} env vars per repo")
        for key, value in v.items():
            if len(key) > ENV_VAR_MAX_KEY_LEN:
                raise ValueError(
                    f"Env var key exceeds maximum length of {ENV_VAR_MAX_KEY_LEN}: {key!r}"
                )
            if not ENV_VAR_KEY_RE.fullmatch(key):
                raise ValueError(
                    f"Env var key {key!r} must match ^[A-Za-z_][A-Za-z0-9_]*$"
                )
            if len(value) > ENV_VAR_MAX_VALUE_LEN:
                raise ValueError(
                    f"Env var value for key {key!r} exceeds maximum length of {ENV_VAR_MAX_VALUE_LEN}"
                )
        return v


class AddTokenRequest(BaseModel):
    """Request body for adding a Claude token to the pool."""

    token: str = Field(min_length=1, max_length=4096)
