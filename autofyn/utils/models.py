"""Data models for the agent package.

Per CLAUDE.md, every dataclass and Pydantic schema in the agent lives
here. Modules keep behavior (classes with I/O, state machines, handlers);
models.py owns the shapes that flow between them.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Literal, TYPE_CHECKING

from pydantic import BaseModel, field_validator

from db.constants import DEFAULT_MODEL, VALID_MODELS
from utils.constants import INJECT_PAYLOAD_MAX_LEN

_FALLBACK_MAP: dict[str, str | None] = {
    "opus": "sonnet",
    "sonnet": None,
    "opus-4-5": "sonnet",
}


def get_fallback_model(model: str) -> str | None:
    """Return the fallback model for rate-limit recovery, or None if no fallback."""
    return _FALLBACK_MAP.get(model)


if TYPE_CHECKING:
    from memory.archiver import RoundArchiver
    from memory.metadata import MetadataStore
    from memory.report import ReportStore
    from user.inbox import UserInbox
    from session.time_lock import TimeLock


# ── Sandbox execute request/response ────────────────────────────────


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


# ── Sandbox repo phase results ──────────────────────────────────────


@dataclass
class SaveResult:
    """Structured response from /repo/save (per-round commit + push).

    `committed` is False when the working tree was clean or git had
    nothing to commit. `pushed` is False when push failed; the error is
    in `push_error`. Push failures are reported, not raised — the caller
    decides whether to retry next round or treat it as fatal.
    """

    committed: bool
    pushed: bool
    push_error: str | None


@dataclass
class TeardownResult:
    """Structured response from /repo/teardown (end-of-run commit + push + PR).

    Every stage (auto-commit, push, PR) is a separate field so the caller
    can report exactly what happened. Non-fatal failures (push, PR) are
    reported via the `*_error` fields rather than raised, so `diff_stats`
    is always populated when the endpoint returns 200.
    """

    auto_committed: bool
    commits_ahead: int
    pushed: bool
    push_error: str | None
    pr_url: str | None
    pr_error: str | None
    diff_stats: list[dict]


# ── Run context ─────────────────────────────────────────────────────


@dataclass
class RunContext:
    """Run-wide mutable state. One instance per run, mutated across rounds."""

    run_id: str
    agent_role: str
    branch_name: str
    base_branch: str
    duration_minutes: float
    github_repo: str
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


# ── Round execution ─────────────────────────────────────────────────


RoundStatus = Literal[
    "complete",  # round finished normally (ResultMessage)
    "ended",  # orchestrator called end_session — stop the whole run
    "paused",  # user paused; outer loop will await resume
    "stopped",  # user stopped; outer loop will tear down
    "rate_limited",  # rate limit rejected; outer loop will back off or abort
    "error",  # exception during round execution
    "session_error",  # SDK/API error (e.g. 401, 500); outer loop retries with backoff
]


@dataclass
class RoundResult:
    """Outcome of a single round of orchestrator execution."""

    status: RoundStatus
    session_id: str | None
    rate_limit_resets_at: int | None = None
    error: str | None = None
    round_summary: str | None = None


@dataclass
class RoundEntry:
    """One line in rounds.json — a single round's summary."""

    n: int
    summary: str
    ended_at: str


@dataclass
class RoundsMetadata:
    """Parsed `/tmp/rounds.json`. Mutated in-place by the round loop."""

    pr_title: str = ""
    pr_description: str = ""
    rounds: list[RoundEntry] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "RoundsMetadata":
        """Return a fresh empty metadata object."""
        return cls()

    def latest_summary(self) -> str:
        """One-line summary for the most recent round. Empty if none."""
        if not self.rounds:
            return ""
        return self.rounds[-1].summary

    def has_round(self, n: int) -> bool:
        """True if an entry for round `n` exists."""
        return any(r.n == n for r in self.rounds)

    def to_json(self) -> str:
        """Serialize to a pretty-printed JSON string."""
        return json.dumps(
            {
                "pr_title": self.pr_title,
                "pr_description": self.pr_description,
                "rounds": [asdict(r) for r in self.rounds],
            },
            indent=2,
            ensure_ascii=False,
        )


@dataclass
class RoundContext:
    """Everything the orchestrator prompt builder needs for one round."""

    round_number: int
    duration_minutes: float
    time_remaining_minutes: float
    metadata: RoundsMetadata
    previous_round_reports: list[str]
    user_messages: list[str]


# ── Bootstrap ───────────────────────────────────────────────────────


@dataclass
class BootstrapResult:
    """Everything the round loop needs after a successful bootstrap."""

    run: RunContext
    inbox: UserInbox
    time_lock: TimeLock
    reports: ReportStore
    metadata: MetadataStore
    archiver: RoundArchiver
    base_session_options: dict
    task: str
    model: str
    fallback_model: str | None
    run_start_time: float
    # Highest round number already archived on disk; 0 for a fresh run,
    # >0 when resuming — the round loop starts counting from the next.
    starting_round: int


# ── User events ─────────────────────────────────────────────────


EventKind = Literal["inject", "pause", "resume", "stop", "unlock"]


@dataclass(frozen=True)
class UserEvent:
    """One user-sourced signal routed through the inbox."""

    kind: EventKind
    payload: str


OutcomeKind = Literal["continue", "break_pause", "break_stop"]


@dataclass(frozen=True)
class ControlOutcome:
    """What the session runner should do after an user event."""

    kind: OutcomeKind
    reason: str


# ── Stream signals ──────────────────────────────────────────────────


SignalKind = Literal[
    "continue",
    "round_complete",
    "run_ended",
    "subagent_boundary",
    "rate_limited",
    "session_error",
]


@dataclass(frozen=True)
class StreamSignal:
    """Decision returned after dispatching one SSE event."""

    kind: SignalKind
    rate_limit_data: dict | None = None
    round_summary: str | None = None
    error: str | None = None


# ── Subagent tracking ───────────────────────────────────────────────


@dataclass
class StuckSubagent:
    """Subagent idle longer than SUBAGENT_IDLE_KILL_SEC."""

    agent_id: str
    agent_type: str
    idle_seconds: int
    total_seconds: int


@dataclass(frozen=True)
class SubagentDef:
    """Definition of a single subagent (name, phase, model, tools)."""

    name: str
    phase: str
    description: str
    model: str
    tools: list[str]


# ── In-process run registry ─────────────────────────────────────────


@dataclass
class ActiveRun:
    """Tracks one in-progress run in the server's run dict."""

    run_id: str | None = None
    status: str = "starting"
    started_at: float = field(default_factory=time.time)
    error_message: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)
    inbox: UserInbox | None = field(default=None, repr=False)
    time_lock: TimeLock | None = field(default=None, repr=False)
    run_context: RunContext | None = field(default=None, repr=False)


# ── HTTP request schemas ────────────────────────────────────────────


class StartRequest(BaseModel):
    """POST /start request body."""

    prompt: str | None = None
    max_budget_usd: float = 0
    duration_minutes: float = 0
    base_branch: str = "main"
    model: str = DEFAULT_MODEL
    claude_token: str | None = None
    git_token: str | None = None
    github_repo: str | None = None
    env: dict[str, str] | None = None

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

    @field_validator("base_branch")
    @classmethod
    def base_branch_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("base_branch must not be empty")
        return v.strip()


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


class HealthRunEntry(BaseModel):
    """Per-run details in the health response."""

    run_id: str
    status: str
    started_at: float
    elapsed_minutes: float | None = None
    time_remaining: str | None = None
    session_unlocked: bool | None = None


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str
    active_runs: int
    max_concurrent: int
    runs: list[HealthRunEntry]
