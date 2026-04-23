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

from db.constants import RUN_STATUS_STARTING, SUPPORTED_SONNET
from utils.models_http import (
    StartRequest,
    InjectRequest,
    StopRequest,
    ResumeRequest,
    HealthRunEntry,
    HealthResponse,
    InternalAuditRequest,
    InternalToolCallRequest,
)

# Re-export HTTP schemas so all callers using `from utils.models import <Class>`
# continue to work unchanged after the split into sibling modules.
__all__ = [
    "StartRequest",
    "InjectRequest",
    "StopRequest",
    "ResumeRequest",
    "HealthRunEntry",
    "HealthResponse",
    "InternalAuditRequest",
    "InternalToolCallRequest",
]

_FALLBACK_MAP: dict[str, str | None] = {
    "claude-opus-4-6": SUPPORTED_SONNET,
    "claude-sonnet-4-6": None,
    "claude-opus-4-5": SUPPORTED_SONNET,
}


def get_fallback_model(model: str) -> str | None:
    """Return the fallback model for rate-limit recovery, or None if no fallback."""
    return _FALLBACK_MAP.get(model)


if TYPE_CHECKING:
    from memory.archiver import RoundArchiver
    from memory.metadata import MetadataStore
    from memory.report import ReportStore
    from user.inbox import UserInbox
    from agent_session.time_lock import TimeLock
    from utils.run_config import RunAgentConfig


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
    skip_pr: bool = False


# ── Round execution ─────────────────────────────────────────────────


RoundStatus = Literal[
    "complete",  # round finished normally (ResultMessage)
    "ended",  # orchestrator called end_session — stop the whole run
    "paused",  # user paused; outer loop will await resume
    "stopped",  # user stopped; outer loop will tear down
    "error",  # exception during round execution
    "session_error",  # SDK/API error (e.g. 401, 500); outer loop retries with backoff
]


@dataclass
class RoundResult:
    """Outcome of a single round of orchestrator execution."""

    status: RoundStatus
    session_id: str | None
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


@dataclass(frozen=True, slots=True)
class UserAction:
    """One entry in the user activity timeline for a run."""

    timestamp: str
    kind: str
    text: str


@dataclass
class RoundContext:
    """Everything the orchestrator prompt builder needs for one round."""

    round_number: int
    duration_minutes: float
    time_remaining_minutes: float
    metadata: RoundsMetadata
    previous_round_reports: list[str]
    user_activity: list[UserAction]
    host_mounts: list[dict[str, str]] | None
    user_env_keys: list[str]


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
    run_config: RunAgentConfig


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
    "rate_limit_info",
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
    status: str = RUN_STATUS_STARTING
    started_at: float = field(default_factory=time.time)
    error_message: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)
    inbox: UserInbox | None = field(default=None, repr=False)
    time_lock: TimeLock | None = field(default=None, repr=False)
    run_context: RunContext | None = field(default=None, repr=False)
    skip_pr: bool = False


