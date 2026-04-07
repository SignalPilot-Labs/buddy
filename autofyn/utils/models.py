"""All data models for the agent package — runtime context, results, and HTTP request schemas."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, field_validator

from utils.constants import INJECT_PAYLOAD_MAX_LEN

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from tools.session import SessionGate


# ── Sandbox Communication ──

@dataclass
class ExecRequest:
    """Command execution request sent to the sandbox."""

    args: list[str]
    cwd: str
    timeout: int
    env: dict[str, str]


@dataclass
class ExecResult:
    """Command execution result returned from the sandbox."""

    stdout: str
    stderr: str
    exit_code: int


# ── Runtime Context ──

@dataclass
class RunContext:
    """Shared state for a single agent run. Passed to all services via DI."""

    run_id: str
    agent_role: str
    branch_name: str
    base_branch: str
    duration_minutes: float
    github_repo: str
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class StreamResult:
    """Structured return from StreamProcessor.process()."""

    should_stop: bool
    final_status: str | None
    session_ended: bool
    result_message: Any | None


@dataclass
class ControlAction:
    """Result of checking a control event. Used by ControlHandler."""

    stop: bool
    break_stream: bool
    final_status: str | None

    @classmethod
    def no_action(cls) -> "ControlAction":
        """No control action needed."""
        return cls(stop=False, break_stream=False, final_status=None)


# ── Active Run (in-process tracking for concurrent runs) ──

@dataclass
class ActiveRun:
    """Tracks one in-progress run in the server's run dict."""

    run_id: str | None = None
    status: str = "starting"
    started_at: float = field(default_factory=time.time)
    error_message: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)
    events: EventBus | None = field(default=None, repr=False)
    session: SessionGate | None = field(default=None, repr=False)


# ── HTTP Request Schemas ──

class StartRequest(BaseModel):
    """POST /start request body."""

    prompt: str | None = None
    max_budget_usd: float = 0
    duration_minutes: float = 0
    base_branch: str = "main"
    extended_context: bool = False
    claude_token: str | None = None
    git_token: str | None = None
    github_repo: str | None = None
    env: dict[str, str] | None = None

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

    @field_validator("base_branch")
    @classmethod
    def base_branch_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("base_branch must not be empty")
        return v.strip()


class ResumeRequest(BaseModel):
    """POST /resume request body."""

    run_id: str
    prompt: str | None = None
    max_budget_usd: float = 0
    claude_token: str | None = None
    git_token: str | None = None
    github_repo: str | None = None
    env: dict[str, str] | None = None

    @field_validator("max_budget_usd")
    @classmethod
    def budget_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("max_budget_usd must be non-negative")
        return v

    @field_validator("run_id")
    @classmethod
    def run_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("run_id must not be empty")
        return v.strip()


class InjectRequest(BaseModel):
    """POST /inject request body."""

    payload: str | None = None

    @field_validator("payload")
    @classmethod
    def payload_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > INJECT_PAYLOAD_MAX_LEN:
            raise ValueError(f"payload must be under {INJECT_PAYLOAD_MAX_LEN} characters")
        return v
