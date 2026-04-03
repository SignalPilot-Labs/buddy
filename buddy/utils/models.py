"""All data models for the agent package — runtime context, results, and HTTP request schemas."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


# ── Runtime Context ──

@dataclass
class RunContext:
    """Shared state for a single agent run. Passed to all services via DI."""

    run_id: str
    agent_role: str
    branch_name: str
    base_branch: str
    duration_minutes: float
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class RoundResult:
    """Structured return from runner.process_round()."""

    should_stop: bool
    final_status: str | None
    session_ended: bool
    result_message: Any | None
    round_tools: list[str] = field(default_factory=list)
    round_text_chunks: list[str] = field(default_factory=list)
    pending_injects: list[str] = field(default_factory=list)


# ── HTTP Request Schemas ──

class StartRequest(BaseModel):
    """POST /start request body."""

    prompt: str | None = None
    max_budget_usd: float = 0
    duration_minutes: float = 0
    base_branch: str = "main"
    claude_token: str | None = None
    git_token: str | None = None
    github_repo: str | None = None


class ResumeRequest(BaseModel):
    """POST /resume request body."""

    run_id: str
    prompt: str | None = None
    max_budget_usd: float = 0
    claude_token: str | None = None
    git_token: str | None = None
    github_repo: str | None = None


class InjectRequest(BaseModel):
    """POST /inject request body."""

    payload: str | None = None
