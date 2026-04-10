"""Run bootstrap — prepare sandbox + services before the round loop starts.

Responsibilities:

    1. Clone the repo in the sandbox and create the working branch.
    2. Persist the branch name to the runs table.
    3. Build the RunContext, OperatorInbox, TimeLock, ReportStore, MetadataStore.
    4. Seed operator-messages.md as an empty file.
    5. Build the (mostly static) SDK session options dict. The orchestrator
       system prompt is rebuilt per round; this dict holds everything else.

Nothing in this module talks to the LLM. It only prepares services.
"""

import logging
import re
import time
import uuid

from memory.metadata import MetadataStore
from memory.report import ReportStore
from operator.inbox import OperatorInbox
from prompts.subagent import build_agent_defs
from sandbox_client.client import SandboxClient
from session.time_lock import TimeLock
from utils import db
from utils.constants import (
    BRANCH_SLUG_MAX_LEN,
    DEFAULT_AGENT_ROLE,
    OPERATOR_MESSAGES_PATH,
    PROMPT_SUMMARY_LIMIT,
    SESSION_EFFORT,
    SESSION_PERMISSION_MODE,
    WORK_DIR,
)
from utils.models import BootstrapResult, RunContext, get_fallback_model

log = logging.getLogger("lifecycle.bootstrap")


async def bootstrap_run(
    sandbox: SandboxClient,
    run_id: str,
    custom_prompt: str,
    max_budget_usd: float,
    duration_minutes: float,
    base_branch: str,
    github_repo: str,
    model: str,
    git_token: str,
    clone_timeout: int,
) -> BootstrapResult:
    """Prepare sandbox state and services for a fresh run."""
    if not custom_prompt:
        raise RuntimeError("bootstrap_run requires a non-empty task prompt")
    if not git_token:
        raise RuntimeError("bootstrap_run requires a GIT_TOKEN")

    fallback_model = get_fallback_model(model)

    branch_name = _make_branch_name(custom_prompt)
    log.info("Run %s cloning %s", run_id, github_repo)
    await sandbox.repo.clone(
        github_repo, git_token, base_branch, clone_timeout,
    )
    await sandbox.repo.ensure_base_branch(base_branch, clone_timeout)
    await sandbox.repo.create_branch(branch_name, base_branch, clone_timeout)
    await db.update_run_branch(run_id, branch_name)
    log.info("Run %s on branch %s", run_id, branch_name)

    run = RunContext(
        run_id=run_id,
        agent_role=DEFAULT_AGENT_ROLE,
        branch_name=branch_name,
        base_branch=base_branch,
        duration_minutes=duration_minutes,
        github_repo=github_repo,
    )
    inbox = OperatorInbox()
    time_lock = TimeLock(duration_minutes)
    reports = ReportStore(sandbox)
    metadata = MetadataStore(sandbox)

    await reports.ensure_directories()
    await sandbox.file_system.write(OPERATOR_MESSAGES_PATH, "", append=False)

    run_start_time = time.time()
    base_session_options = _build_base_session_options(
        run=run,
        model=model,
        fallback_model=fallback_model,
        max_budget_usd=max_budget_usd,
        run_start_time=run_start_time,
    )

    await _log_run_started(
        run_id, branch_name, model, max_budget_usd,
        duration_minutes, custom_prompt,
    )

    return BootstrapResult(
        run=run,
        inbox=inbox,
        time_lock=time_lock,
        reports=reports,
        metadata=metadata,
        base_session_options=base_session_options,
        task=custom_prompt,
        model=model,
        fallback_model=fallback_model,
        run_start_time=run_start_time,
    )


# ── Branch naming ────────────────────────────────────────────────────


def _make_branch_name(custom_prompt: str) -> str:
    """Generate a unique `autofyn/<slug>-<id>` branch name for a run."""
    short_id = uuid.uuid4().hex[:6]
    slug = _slugify(custom_prompt, BRANCH_SLUG_MAX_LEN)
    if slug:
        return f"autofyn/{slug}-{short_id}"
    return f"autofyn/{short_id}"


def _slugify(text: str, max_len: int) -> str:
    """Convert free text to a kebab-case slug of at most `max_len` chars."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    slug = slug[:max_len]
    return slug.rstrip("-")


# ── Session options ──────────────────────────────────────────────────


def _build_base_session_options(
    run: RunContext,
    model: str,
    fallback_model: str | None,
    max_budget_usd: float,
    run_start_time: float,
) -> dict:
    """Return everything the sandbox /session/start body needs except prompts.

    The orchestrator system prompt is rebuilt per round and spliced in by
    the round loop before starting each session.
    """
    return {
        "model": model,
        "fallback_model": fallback_model if fallback_model != model else None,
        "effort": SESSION_EFFORT,
        "include_partial_messages": True,
        "permission_mode": SESSION_PERMISSION_MODE,
        "cwd": WORK_DIR,
        "add_dirs": ["/workspace", "/home/agentuser/research", "/opt/autofyn"],
        "setting_sources": ["project"],
        "max_budget_usd": max_budget_usd if max_budget_usd > 0 else None,
        "resume": None,
        "agents": build_agent_defs(),
        "run_id": run.run_id,
        "github_repo": run.github_repo,
        "branch_name": run.branch_name,
        "session_gate": {
            "duration_minutes": run.duration_minutes,
            "start_time": run_start_time,
        },
    }


# ── Audit ────────────────────────────────────────────────────────────


async def _log_run_started(
    run_id: str,
    branch: str,
    model: str,
    budget: float,
    duration: float,
    custom_prompt: str,
) -> None:
    """Emit run_started and prompt_submitted audit events."""
    await db.log_audit(run_id, "run_started", {
        "branch": branch,
        "model": model,
        "max_budget_usd": budget,
        "duration_minutes": duration,
        "custom_prompt": custom_prompt[:PROMPT_SUMMARY_LIMIT],
    })
    await db.log_audit(run_id, "prompt_submitted", {
        "prompt": custom_prompt[:PROMPT_SUMMARY_LIMIT],
    })
