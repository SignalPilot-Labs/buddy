"""Pydantic HTTP request/response schemas for the agent API.

Owns the API contract validation layer — all BaseModel subclasses that
describe the shape of HTTP request bodies and response payloads.
"""

from pydantic import BaseModel, Field, field_validator, model_validator

from db.constants import DEFAULT_EFFORT, DEFAULT_MODEL, STARTER_PRESET_KEYS, VALID_EFFORTS, VALID_MODELS
from utils.constants import INJECT_PAYLOAD_MAX_LEN


class StartRequest(BaseModel):
    """POST /start request body."""

    prompt: str | None = None
    preset: str | None = None
    max_budget_usd: float = 0
    duration_minutes: float = 0
    base_branch: str = "main"
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    claude_token: str | None = Field(default=None, repr=False)
    git_token: str | None = Field(default=None, repr=False)
    github_repo: str | None = None
    env: dict[str, str] | None = None
    host_mounts: list[dict[str, str]] | None = None

    @field_validator("model")
    @classmethod
    def model_valid(cls, v: str) -> str:
        if v not in VALID_MODELS:
            raise ValueError(f"model must be one of {VALID_MODELS}")
        return v

    @field_validator("max_budget_usd")
    @classmethod
    def budget_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("max_budget_usd must be non-negative")
        return v

    @field_validator("duration_minutes")
    @classmethod
    def duration_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("duration_minutes must be non-negative")
        return v

    @field_validator("effort")
    @classmethod
    def effort_valid(cls, v: str) -> str:
        if v not in VALID_EFFORTS:
            raise ValueError(f"effort must be one of {VALID_EFFORTS}")
        return v

    @field_validator("base_branch")
    @classmethod
    def base_branch_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("base_branch must not be empty")
        return v.strip()

    @field_validator("preset")
    @classmethod
    def preset_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in STARTER_PRESET_KEYS:
            raise ValueError(f"preset must be one of {STARTER_PRESET_KEYS}")
        return v

    @model_validator(mode="after")
    def prompt_or_preset_exclusive(self) -> "StartRequest":
        """Ensure prompt and preset are mutually exclusive."""
        if self.prompt and self.preset:
            raise ValueError("Cannot set both prompt and preset")
        return self


class InjectRequest(BaseModel):
    """POST /inject request body."""

    payload: str | None = None

    @field_validator("payload")
    @classmethod
    def payload_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > INJECT_PAYLOAD_MAX_LEN:
            raise ValueError(
                f"payload must be under {INJECT_PAYLOAD_MAX_LEN} characters"
            )
        return v


class StopRequest(BaseModel):
    """POST /stop request body."""

    skip_pr: bool


class ResumeRequest(BaseModel):
    """POST /resume request body for restarting a terminal run."""

    run_id: str
    prompt: str | None
    claude_token: str | None = Field(repr=False)
    git_token: str | None = Field(repr=False)
    github_repo: str | None
    env: dict[str, str] | None


class HealthRunEntry(BaseModel):
    """Per-run details in the health response."""

    run_id: str
    status: str
    started_at: float
    elapsed_minutes: float | None = None
    time_remaining: str | None = None
    run_unlocked: bool | None = None


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str
    active_runs: int
    max_concurrent: int
    runs: list[HealthRunEntry]


class InternalAuditRequest(BaseModel):
    """POST /internal/audit request body (sandbox → agent)."""

    run_id: str
    event_type: str
    details: dict | None


class InternalToolCallRequest(BaseModel):
    """POST /internal/tool-call request body (sandbox → agent)."""

    run_id: str
    phase: str
    tool_name: str
    input_data: dict | None
    output_data: dict | None
    duration_ms: int | None
    permitted: bool
    deny_reason: str | None
    agent_role: str
    tool_use_id: str | None
    session_id: str | None
    agent_id: str | None
