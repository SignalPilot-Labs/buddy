"""Run bootstrap — prepare sandbox + services before the round loop starts.

Responsibilities:

    1. Clone the repo in the sandbox and create the working branch.
    2. Persist the branch name to the runs table.
    3. Build the RunContext, UserInbox, TimeLock, ReportStore, MetadataStore.
    4. Seed /tmp/rounds.json with the empty schema.
    5. Build the (mostly static) SDK session options dict. The orchestrator
       system prompt is rebuilt per round; this dict holds everything else.

Nothing in this module talks to the LLM. It only prepares services.
"""

import logging
import re
import time
import uuid

from memory.archiver import RoundArchiver
from memory.metadata import MetadataStore
from memory.report import ReportStore
from user.inbox import UserInbox
from sandbox_client.client import SandboxClient
from agent_session.time_lock import TimeLock
from utils import db
from db.constants import MODELS_SUPPORTING_MAX_EFFORT
from utils.constants import (
    BRANCH_SLUG_MAX_LEN,
    DEFAULT_AGENT_ROLE,
    SESSION_PERMISSION_MODE,
    WORK_DIR,
)
from utils.models import (
    BootstrapResult,
    RoundsMetadata,
    RunContext,
    get_fallback_model,
)

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
    effort: str,
    git_token: str,
    clone_timeout: int,
) -> BootstrapResult:
    """Prepare sandbox state and services for a fresh run."""
    if not custom_prompt:
        raise RuntimeError("bootstrap_run requires a non-empty task prompt")
    if not git_token:
        raise RuntimeError("bootstrap_run requires a GIT_TOKEN")

    fallback_model = get_fallback_model(model)

    # Resume: reuse existing branch if the DB already has one for this run.
    existing_branch = await db.get_run_branch_name(run_id)
    branch_name = existing_branch or _make_branch_name(custom_prompt)
    log.info("Run %s bootstrapping %s on branch %s", run_id, github_repo, branch_name)
    await sandbox.repo.bootstrap(
        repo=github_repo,
        token=git_token,
        base_branch=base_branch,
        working_branch=branch_name,
        timeout=clone_timeout,
    )
    if existing_branch:
        await db.update_run_status(run_id, "running")
    else:
        await db.update_run_branch(run_id, branch_name)

    # On resume, seed cost/token accumulators from the DB so teardown
    # doesn't overwrite the previous run's totals with zeros.
    prior = await db.get_run_for_resume(run_id) if existing_branch else None
    run = RunContext(
        run_id=run_id,
        agent_role=DEFAULT_AGENT_ROLE,
        branch_name=branch_name,
        base_branch=base_branch,
        duration_minutes=duration_minutes,
        github_repo=github_repo,
        total_cost=float(prior["total_cost_usd"] or 0) if prior else 0.0,
        total_input_tokens=int(prior["total_input_tokens"] or 0) if prior else 0,
        total_output_tokens=int(prior["total_output_tokens"] or 0) if prior else 0,
        cache_creation_input_tokens=int(prior["cache_creation_input_tokens"] or 0) if prior else 0,
        cache_read_input_tokens=int(prior["cache_read_input_tokens"] or 0) if prior else 0,
    )
    inbox = UserInbox()
    time_lock = TimeLock(duration_minutes)
    reports = ReportStore(sandbox)
    metadata = MetadataStore(sandbox)
    archiver = RoundArchiver(sandbox, run_id)

    # Resume: if the agent volume already has rounds for this run_id,
    # push them back into the new sandbox's /tmp and start counting
    # from the next round. Fresh run: returns 0, we seed rounds.json.
    starting_round = await archiver.restore_all()
    if starting_round == 0:
        # Seed an empty rounds.json so the first-round orchestrator sees
        # the canonical schema instead of a missing file.
        await metadata.save(RoundsMetadata.empty())
    else:
        log.info("Resumed run %s at round %d", run_id, starting_round + 1)

    run_start_time = time.time()
    base_session_options = _build_base_session_options(
        run=run,
        model=model,
        fallback_model=fallback_model,
        max_budget_usd=max_budget_usd,
        effort=effort,
        run_start_time=run_start_time,
    )

    await _log_run_started(
        run_id,
        branch_name,
        model,
        max_budget_usd,
        duration_minutes,
        custom_prompt,
    )

    return BootstrapResult(
        run=run,
        inbox=inbox,
        time_lock=time_lock,
        reports=reports,
        metadata=metadata,
        archiver=archiver,
        base_session_options=base_session_options,
        task=custom_prompt,
        model=model,
        fallback_model=fallback_model,
        run_start_time=run_start_time,
        starting_round=starting_round,
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
    effort: str,
    run_start_time: float,
) -> dict:
    """Return everything the sandbox /session/start body needs except prompts.

    The orchestrator system prompt is rebuilt per round and spliced in by
    the round loop before starting each session.
    """
    resolved_effort = effort
    if effort == "max" and model not in MODELS_SUPPORTING_MAX_EFFORT:
        resolved_effort = "high"
    return {
        "model": model,
        "fallback_model": fallback_model if fallback_model != model else None,
        "effort": resolved_effort,
        "include_partial_messages": True,
        "permission_mode": SESSION_PERMISSION_MODE,
        "cwd": WORK_DIR,
        "add_dirs": ["/workspace", "/home/agentuser/research", "/opt/autofyn"],
        "setting_sources": ["project"],
        "max_budget_usd": max_budget_usd if max_budget_usd > 0 else None,
        "resume": None,
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
    await db.log_audit(
        run_id,
        "run_started",
        {
            "branch": branch,
            "model": model,
            "max_budget_usd": budget,
            "duration_minutes": duration,
            "has_custom_prompt": bool(custom_prompt),
        },
    )
    # Full prompt (not truncated) — the frontend uses exact text equality
    # to reconcile a pending optimistic bubble against this event. Any
    # truncation here causes a mismatch and a duplicate "two bubbles" render.
    await db.log_audit(
        run_id,
        "prompt_submitted",
        {"prompt": custom_prompt},
    )
