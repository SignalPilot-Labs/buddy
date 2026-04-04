"""Run bootstrap: git setup, service creation, SDK options.

RunBootstrap prepares everything needed to start or resume an agent run.
It produces a RunContext and ClaudeAgentOptions, then hands off to AgentLoop.
"""

import logging
import os
import shutil
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import HookMatcher, AgentDefinition

from utils import db
from utils.constants import (
    DEFAULT_BASE_BRANCH,
    PROMPT_SUMMARY_LIMIT,
    SKILLS_FALLBACK_PATH,
    SKILLS_SRC_PATH,
)
from utils.git import GitWorkspace
from utils.models import RunContext
from utils.prompts import PromptLoader
from core.event_bus import EventBus
from tools.security import SecurityGate
from tools.session import SessionGate
from tools.db_logger import DBLogger

log = logging.getLogger("core.bootstrap")


class RunBootstrap:
    """Prepares a new or resumed run: git, services, SDK options.

    Public API:
        setup_new(prompt, budget, duration, base_branch) -> tuple of all run objects
        setup_resume(run_id, budget) -> tuple of all run objects
    """

    def __init__(self, git: GitWorkspace):
        self._git = git
        self._prompts = PromptLoader()

    async def setup_new(
        self,
        custom_prompt: str | None,
        max_budget: float,
        duration_minutes: float,
        base_branch: str,
        github_repo: str,
    ) -> tuple[RunContext, ClaudeAgentOptions, SessionGate, EventBus, DBLogger, str]:
        """Bootstrap a new run. Returns (ctx, options, session, events, logger, initial_prompt)."""
        model = os.environ.get("AGENT_MODEL", "opus")
        fallback_model = os.environ.get("AGENT_FALLBACK_MODEL", "sonnet")

        branch_name = self._setup_git(base_branch, github_repo)
        run_id = await db.create_run(
            branch_name, custom_prompt, duration_minutes, base_branch, None
        )
        log.info("Run %s on branch %s", run_id, branch_name)

        ctx = RunContext(
            run_id=run_id,
            agent_role="worker",
            branch_name=branch_name,
            base_branch=base_branch,
            duration_minutes=duration_minutes,
            github_repo=github_repo,
        )
        logger, gate, session, events = self._create_services(ctx)
        events.start_pulse_checker(run_id, logger)

        self._copy_skills()
        options = self._build_sdk_options(
            ctx,
            model,
            fallback_model,
            session,
            gate,
            logger,
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

        initial = (
            custom_prompt if custom_prompt else self._prompts.build_initial_prompt()
        )
        return ctx, options, session, events, logger, initial

    async def setup_resume(
        self,
        run_id: str,
        max_budget: float,
        prompt: str | None = None,
    ) -> tuple[RunContext, ClaudeAgentOptions, SessionGate, EventBus, DBLogger, str]:
        """Bootstrap a resumed run. Returns (ctx, options, session, events, logger, initial_prompt)."""
        run_info = await db.get_run_for_resume(run_id)
        if not run_info:
            raise RuntimeError(f"Run {run_id} not found")

        model = os.environ.get("AGENT_MODEL", "opus")
        fallback_model = os.environ.get("AGENT_FALLBACK_MODEL", "sonnet")

        self._git.setup_auth(run_info.get("github_repo", ""))
        self._checkout_branch(
            run_info["branch_name"], run_info.get("base_branch", DEFAULT_BASE_BRANCH)
        )

        ctx = RunContext(
            run_id=run_id,
            agent_role="worker",
            branch_name=run_info["branch_name"],
            base_branch=run_info.get("base_branch", DEFAULT_BASE_BRANCH),
            duration_minutes=run_info.get("duration_minutes", 0),
            github_repo=run_info.get("github_repo", ""),
            total_cost=run_info.get("total_cost_usd", 0) or 0,
            total_input_tokens=run_info.get("total_input_tokens", 0) or 0,
            total_output_tokens=run_info.get("total_output_tokens", 0) or 0,
        )
        logger, gate, session, events = self._create_services(ctx)
        events.start_pulse_checker(run_id, logger)

        self._copy_skills()
        session_id = run_info.get("sdk_session_id")
        options = self._build_sdk_options(
            ctx,
            model,
            fallback_model,
            session,
            gate,
            logger,
            None,
            session_id,
            max_budget,
            run_info.get("custom_prompt"),
        )

        await db.update_run_status(run_id, "running")
        await db.log_audit(run_id, "session_resumed", {"branch": ctx.branch_name})

        initial = self._build_resume_prompt(run_info, prompt)
        return ctx, options, session, events, logger, initial

    # ── Git ──

    def _setup_git(self, base_branch: str, github_repo: str) -> str:
        """Clone repo, create branch. Returns branch name."""
        self._git.setup_auth(github_repo)
        self._git.ensure_base_branch(base_branch)
        branch_name = self._git.get_branch_name()
        self._git.create_branch(branch_name, base_branch)
        return branch_name

    def _checkout_branch(self, branch_name: str, base_branch: str) -> None:
        """Checkout an existing branch for resume."""
        work_dir = self._git.get_work_dir()
        try:
            self._git.run_git(["fetch", "origin", branch_name], cwd=work_dir)
            self._git.run_git(["checkout", branch_name], cwd=work_dir)
            self._git.run_git(["pull", "origin", branch_name], cwd=work_dir)
        except (RuntimeError, OSError) as e:
            log.warning("Could not fetch/checkout %s: %s — trying local checkout", branch_name, e)
            try:
                self._git.run_git(["checkout", branch_name], cwd=work_dir)
            except (RuntimeError, OSError) as e2:
                log.warning("Local checkout failed too: %s — creating fresh branch", e2)
                self._git.create_branch(branch_name, base_branch)

    def _build_resume_prompt(self, run_info: dict, operator_prompt: str | None) -> str:
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

        parts.append("\nCheck your recent commits with `git log --oneline -5`.")

        if operator_prompt:
            parts.append(f"\n**Operator message:** {operator_prompt}")
        else:
            parts.append("\nContinue where you left off.")

        return "\n".join(parts)

    def _copy_skills(self) -> None:
        """Copy buddy/skills/ → .claude/skills/ in the cloned repo. Always."""
        skills_src = Path(SKILLS_SRC_PATH)
        if not skills_src.exists():
            skills_src = Path(SKILLS_FALLBACK_PATH)
        if not skills_src.exists():
            return

        work_dir = self._git.get_work_dir()
        skills_dst = Path(work_dir) / ".claude" / "skills"
        skills_dst.parent.mkdir(exist_ok=True)
        if skills_dst.exists():
            shutil.rmtree(skills_dst)
        shutil.copytree(skills_src, skills_dst)

    # ── Services ──

    def _create_services(
        self, ctx: RunContext
    ) -> tuple[DBLogger, SecurityGate, SessionGate, EventBus]:
        """Create all per-run services."""
        return DBLogger(ctx), SecurityGate(ctx), SessionGate(ctx), EventBus()

    def _build_subagents(self) -> dict[str, AgentDefinition]:
        """Build subagent definitions."""
        return {
            "builder": AgentDefinition(
                description="Write code, implement features, create files. Use for all code generation tasks.",
                prompt=self._prompts.load_subagent_prompt("builder"),
                model="sonnet",
                tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            ),
            "frontend-builder": AgentDefinition(
                description="Build React/Next.js components, pages, and styling. Use for all frontend work.",
                prompt=self._prompts.load_subagent_prompt("frontend-builder"),
                model="sonnet",
                tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            ),
            "reviewer": AgentDefinition(
                description="Review code, run tests/linter/typechecker, report bugs, security, and quality issues. Call after every build.",
                prompt=self._prompts.load_subagent_prompt("reviewer"),
                model="opus",
                tools=["Read", "Glob", "Grep", "Bash"],
            ),
            "explorer": AgentDefinition(
                description="Explore codebase, find patterns, read docs. Read-only research.",
                prompt=self._prompts.load_subagent_prompt("explorer"),
                model="sonnet",
                tools=["Read", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
            ),
            "planner": AgentDefinition(
                description="Analyze progress and plan the next step. Call between build rounds to decide what to do next.",
                prompt=self._prompts.load_subagent_prompt("planner"),
                model="sonnet",
                tools=["Read", "Write", "Glob", "Grep", "Bash"],
            ),
        }

    def _build_sdk_options(
        self,
        ctx: RunContext,
        model: str,
        fallback_model: str | None,
        session: SessionGate,
        gate: SecurityGate,
        logger: DBLogger,
        subagents: dict | None,
        resume_id: str | None,
        budget: float,
        custom_prompt: str | None,
    ) -> ClaudeAgentOptions:
        """Build SDK client options."""
        return ClaudeAgentOptions(
            model=model,
            fallback_model=(
                fallback_model if fallback_model and fallback_model != model else None
            ),
            effort="medium",
            system_prompt=self._prompts.build_system_prompt(
                custom_prompt, ctx.duration_minutes
            ),
            permission_mode="bypassPermissions",
            can_use_tool=gate.check_permission,
            cwd=self._git.get_work_dir(),
            add_dirs=["/workspace", "/home/agentuser/research"],
            setting_sources=["project"],
            max_budget_usd=budget if budget > 0 else None,
            include_partial_messages=True,
            resume=resume_id,
            mcp_servers={"session_gate": session.create_mcp_server()},
            agents=subagents,
            hooks={
                "PreToolUse": [HookMatcher(hooks=[logger.pre_tool_use])],
                "PostToolUse": [HookMatcher(hooks=[logger.post_tool_use])],
                "SubagentStart": [HookMatcher(hooks=[logger.subagent_start])],
                "SubagentStop": [HookMatcher(hooks=[logger.subagent_stop])],
                "Stop": [HookMatcher(hooks=[logger.stop])],
            },
        )
