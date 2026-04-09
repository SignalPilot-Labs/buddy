"""Run bootstrap: git setup, service creation, sandbox session options.

Bootstrap prepares everything needed to start or resume an agent run.
It produces a RunContext and session options dict, then hands off to SessionRunner.
"""

import logging
import os
import time

from utils import db
from utils.constants import OPERATOR_MESSAGES_PATH, PROMPT_SUMMARY_LIMIT
from utils.models import ExecRequest, GitSetupParams, RunContext
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from sandbox_manager.repo_ops import RepoOps
from core.event_bus import EventBus
from tools.session import SessionGate
from tools.subagent_tracker import SubagentTracker

log = logging.getLogger("core.bootstrap")


class Bootstrap:
    """Prepares a new or resumed run: git, services, sandbox session options.

    Public API:
        setup_new(...) -> tuple of all run objects
        setup_resume(...) -> tuple of all run objects
    """

    def __init__(
        self,
        repo_ops: RepoOps,
        sandbox: SandboxClient,
    ) -> None:
        self._repo_ops = repo_ops
        self._sandbox = sandbox
        self._prompts = PromptLoader()

    async def setup_new(
        self,
        run_id: str,
        custom_prompt: str | None,
        max_budget: float,
        duration_minutes: float,
        base_branch: str,
        github_repo: str,
        exec_timeout: int,
        clone_timeout: int,
    ) -> tuple[RunContext, dict, SessionGate, EventBus, SubagentTracker, str]:
        """Bootstrap a new run. run_id is pre-created by the server."""
        model = os.environ.get("AGENT_MODEL", "opus")
        fallback_model = os.environ.get("AGENT_FALLBACK_MODEL", "sonnet")

        git_params = GitSetupParams(
            base_branch=base_branch,
            github_repo=github_repo,
            exec_timeout=exec_timeout,
            clone_timeout=clone_timeout,
            custom_prompt=custom_prompt,
        )
        branch_name = await self._setup_git(git_params)
        await db.update_run_branch(run_id, branch_name)
        log.info("Run %s on branch %s", run_id, branch_name)

        run_context = RunContext(
            run_id=run_id,
            agent_role="worker",
            branch_name=branch_name,
            base_branch=base_branch,
            duration_minutes=duration_minutes,
            github_repo=github_repo,
        )
        session, events, tracker = self._create_services(run_context)

        session_options = self._build_session_options(
            run_context,
            model,
            fallback_model,
            self._build_subagents(),
            None,
            max_budget,
            custom_prompt,
        )

        await db.log_audit(
            run_id,
            "run_started",
            {
                "branch": branch_name,
                "model": model,
                "max_budget_usd": max_budget,
                "duration_minutes": duration_minutes,
                "custom_prompt": (
                    custom_prompt[:PROMPT_SUMMARY_LIMIT] if custom_prompt else None
                ),
            },
        )

        if custom_prompt:
            await db.log_audit(
                run_id,
                "prompt_submitted",
                {"prompt": custom_prompt[:PROMPT_SUMMARY_LIMIT]},
            )

        initial = (
            custom_prompt if custom_prompt else self._prompts.build_initial_prompt()
        )
        return run_context, session_options, session, events, tracker, initial

    async def setup_resume(
        self,
        run_id: str,
        max_budget: float,
        exec_timeout: int,
        clone_timeout: int,
        prompt: str | None,
    ) -> tuple[RunContext, dict, SessionGate, EventBus, SubagentTracker, str]:
        """Bootstrap a resumed run. Returns (run_context, session_options, session, events, tracker, initial_prompt)."""
        run_info = await db.get_run_for_resume(run_id)
        if not run_info:
            raise RuntimeError(f"Run {run_id} not found")
        if not run_info.get("github_repo"):
            raise RuntimeError(f"Run {run_id} has no github_repo — cannot resume")

        model = os.environ.get("AGENT_MODEL", "opus")
        fallback_model = os.environ.get("AGENT_FALLBACK_MODEL", "sonnet")

        await self._repo_ops.setup_auth(
            run_info["github_repo"],
            exec_timeout,
            clone_timeout,
        )
        await self._repo_ops.checkout_branch(
            run_info["branch_name"],
            run_info.get("base_branch", "main"),
            exec_timeout,
        )

        run_context = RunContext(
            run_id=run_id,
            agent_role="worker",
            branch_name=run_info["branch_name"],
            base_branch=run_info.get("base_branch", "main"),
            duration_minutes=run_info.get("duration_minutes", 0),
            github_repo=run_info["github_repo"],
            total_cost=run_info.get("total_cost_usd", 0) or 0,
            total_input_tokens=run_info.get("total_input_tokens", 0) or 0,
            total_output_tokens=run_info.get("total_output_tokens", 0) or 0,
            cache_creation_input_tokens=run_info.get("cache_creation_input_tokens", 0) or 0,
            cache_read_input_tokens=run_info.get("cache_read_input_tokens", 0) or 0,
        )
        session, events, tracker = self._create_services(run_context)

        session_id = run_info.get("sdk_session_id")
        session_options = self._build_session_options(
            run_context,
            model,
            fallback_model,
            None,
            session_id,
            max_budget,
            run_info.get("custom_prompt"),
        )

        await db.update_run_status(run_id, "running")
        await db.log_audit(
            run_id, "session_resumed", {"branch": run_context.branch_name}
        )
        if prompt:
            await db.log_audit(run_id, "prompt_injected", {
                "prompt": prompt, "delivery": "resume",
            })

        operator_messages = await db.get_operator_messages(run_id)
        await self._restore_operator_messages(operator_messages, exec_timeout)
        initial = self._build_resume_prompt(run_info, prompt, operator_messages)
        return run_context, session_options, session, events, tracker, initial

    # -- Git --

    async def _setup_git(self, params: GitSetupParams) -> str:
        """Clone repo in sandbox, create branch. Returns branch name."""
        await self._repo_ops.setup_auth(
            params.github_repo, params.exec_timeout, params.clone_timeout
        )
        await self._repo_ops.ensure_base_branch(params.base_branch, params.exec_timeout)
        branch_name = self._repo_ops.get_branch_name(params.custom_prompt)
        await self._repo_ops.create_branch(
            branch_name, params.base_branch, params.exec_timeout
        )
        return branch_name

    async def _restore_operator_messages(
        self, messages: list[dict], exec_timeout: int,
    ) -> None:
        """Recreate /tmp/operator-messages.md from DB on resume."""
        if not messages:
            return
        lines = [f"[{msg['ts']}] {msg['prompt']}" for msg in messages]
        content = "\n".join(lines) + "\n"
        escaped = content.replace("'", "'\\''")
        await self._sandbox.exec(ExecRequest(
            args=["sh", "-c", f"mkdir -p /tmp && printf '%s' '{escaped}' > {OPERATOR_MESSAGES_PATH}"],
            cwd="/tmp",
            timeout=exec_timeout,
            env={},
        ))
        log.info("Restored %d operator messages to %s", len(messages), OPERATOR_MESSAGES_PATH)

    # -- Services --

    def _create_services(
        self, run_context: RunContext
    ) -> tuple[SessionGate, EventBus, SubagentTracker]:
        """Create per-run services and start the pulse checker."""
        tracker = SubagentTracker()
        events = EventBus()
        events.start_pulse_checker(run_context.run_id, tracker)
        return SessionGate(run_context), events, tracker

    def _build_subagents(self) -> dict[str, dict]:
        """Build subagent definitions as plain dicts for sandbox."""
        return {
            # Explore phase
            "code-explorer": {
                "description": "Map codebase structure, find implementations, trace dependencies. Call when you need to understand how code is organized or where something lives. Read-only — writes findings to /tmp/explore/round-N-code-explorer.md.",
                "prompt": self._prompts.load_subagent_prompt("explore/code-explorer"),
                "model": "sonnet",
                "tools": ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
            },
            "debugger": {
                "description": "Diagnose bugs and failures. Find root causes, read logs, reproduce issues. Call when something is broken and you need to find why. Writes findings to /tmp/explore/round-N-debugger.md.",
                "prompt": self._prompts.load_subagent_prompt("explore/debugger"),
                "model": "sonnet",
                "tools": ["Read", "Write", "Glob", "Grep", "Bash"],
            },
            # Plan phase
            "architect": {
                "description": "Design the next unit of work. Analyze current state, make structural decisions, write spec to /tmp/plan/round-N-architect.md. Call to plan before building.",
                "prompt": self._prompts.load_subagent_prompt("plan/architect"),
                "model": "opus",
                "tools": ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
            },
            # Build phase
            "backend-dev": {
                "description": "Implement Python, APIs, database, infrastructure code. Reads spec from /tmp/plan/round-N-architect.md, writes build report to /tmp/build/round-N-backend-dev.md. Never use for React/Next.js/CSS/UI work.",
                "prompt": self._prompts.load_subagent_prompt("build/backend-dev"),
                "model": "sonnet",
                "tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            },
            "frontend-dev": {
                "description": "Implement React, Next.js, TypeScript UI, CSS, styling. Reads spec from /tmp/plan/round-N-architect.md, writes build report to /tmp/build/round-N-frontend-dev.md. Never use for Python/backend work.",
                "prompt": self._prompts.load_subagent_prompt("build/frontend-dev"),
                "model": "sonnet",
                "tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            },
            # Review phase
            "code-reviewer": {
                "description": "Review code for correctness, security, and quality. Runs tests, typechecker, linter. Writes verdict to /tmp/review/round-N-code-reviewer.md. Call after every build.",
                "prompt": self._prompts.load_subagent_prompt("review/code-reviewer"),
                "model": "opus",
                "tools": ["Read", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
            },
            "ui-reviewer": {
                "description": "Review frontend for visual consistency, spacing, hierarchy, accessibility, and AI slop. Writes to /tmp/review/round-N-ui-reviewer.md. Call alongside code-reviewer when frontend-dev made changes.",
                "prompt": self._prompts.load_subagent_prompt("review/ui-reviewer"),
                "model": "opus",
                "tools": ["Read", "Write", "Glob", "Grep", "Bash"],
            },
            "security-reviewer": {
                "description": "Audit code for security vulnerabilities: injection, auth gaps, leaked secrets, unsafe config. Writes to /tmp/review/round-N-security-reviewer.md. Call when changes touch auth, user input, APIs, or secrets.",
                "prompt": self._prompts.load_subagent_prompt("review/security-reviewer"),
                "model": "opus",
                "tools": ["Read", "Write", "Glob", "Grep", "Bash"],
            },
        }

    def _build_session_options(
        self,
        run_context: RunContext,
        model: str,
        fallback_model: str | None,
        subagents: dict | None,
        resume_id: str | None,
        budget: float,
        custom_prompt: str | None,
    ) -> dict:
        """Build session options dict to send to sandbox."""
        system_prompt = self._prompts.build_system_prompt(
            custom_prompt,
            run_context.duration_minutes,
        )
        return {
            "model": model,
            "fallback_model": (
                fallback_model if fallback_model and fallback_model != model else None
            ),
            "effort": "medium",
            "include_partial_messages": True,
            "permission_mode": "bypassPermissions",
            "system_prompt": {
                "type": system_prompt["type"],
                "preset": system_prompt["preset"],
                "append": system_prompt.get("append", ""),
            },
            "cwd": self._repo_ops.get_work_dir(),
            "add_dirs": ["/workspace", "/home/agentuser/research", "/opt/autofyn"],
            "setting_sources": ["project"],
            "max_budget_usd": budget if budget > 0 else None,
            "resume": resume_id,
            "agents": subagents,
            "run_id": run_context.run_id,
            "github_repo": run_context.github_repo,
            "branch_name": run_context.branch_name,
            "session_gate": {
                "duration_minutes": run_context.duration_minutes,
                "start_time": time.time(),
            },
        }

    def _build_resume_prompt(
        self, run_info: dict, operator_prompt: str | None, operator_messages: list[dict],
    ) -> str:
        """Build a context-rich resume prompt from run history."""
        parts = ["You are resuming a previous session. Here is your context:\n"]

        branch = run_info.get("branch_name", "unknown")
        parts.append(f"- **Branch:** `{branch}`")

        prev_status = run_info.get("status", "unknown")
        parts.append(f"- **Previous status:** {prev_status}")

        original_task = run_info.get("custom_prompt")
        if original_task:
            task_preview = original_task[:PROMPT_SUMMARY_LIMIT]
            parts.append(f"- **Original task:** {task_preview}")

        cost = run_info.get("total_cost_usd") or 0
        if cost > 0:
            parts.append(f"- **Cost so far:** ${cost:.2f}")

        if operator_messages:
            parts.append("\n**Previous operator messages (oldest first):**")
            for msg in operator_messages:
                parts.append(f"- {msg['prompt']}")

        parts.append("\nCheck your recent commits with `git log --oneline -5`.")

        if operator_prompt:
            parts.append(f"\n**Operator message:** {operator_prompt}")
        else:
            parts.append("\nContinue where you left off.")

        return "\n".join(parts)
