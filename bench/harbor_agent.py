"""Harbor Installed Agent for running Buddy on Terminal-Bench.

Install and run:
    harbor run -d harbor-framework/terminal-bench-2 --agent-import-path bench.harbor_agent:BuddyAgent

Environment variables required (passed through Harbor):
    ANTHROPIC_API_KEY    — Claude API key (used as CLAUDE_CODE_OAUTH_TOKEN)
    GITHUB_REPO          — optional, "owner/repo" if the task targets a specific repo
"""

import asyncio
import shlex

from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

REPO_URL = "https://github.com/SignalPilot-Labs/Buddy"
SANDBOX_URL = "http://localhost:8080"
BENCH_SECRET = "harbor-bench"
SANDBOX_STARTUP_WAIT_SEC = 8
HEALTH_POLL_INTERVAL_SEC = 2
HEALTH_POLL_ATTEMPTS = 30


class BuddyAgent(BaseInstalledAgent):
    """Buddy agent adapter for Harbor. Installs the sandbox + orchestrator into the
    Harbor task container and drives them with the terminal-bench instruction."""

    @staticmethod
    def name() -> str:
        return "buddy"

    def version(self) -> str | None:
        return None

    async def install(self, environment: BaseEnvironment) -> None:
        """Install system deps, Buddy sandbox, and headless orchestrator. No DB required."""
        # System deps — use generic python3 packages (works on both Debian and Ubuntu)
        await self.exec_as_root(
            environment,
            "apt-get update -qq && apt-get install -y -qq "
            "python3-venv python3-dev git curl",
        )

        # Ensure pip is available (python:3.13-slim may not have it)
        await self.exec_as_root(
            environment,
            "python3 -m ensurepip --upgrade 2>/dev/null || "
            "apt-get install -y -qq python3-pip",
        )

        # Install Node.js via nodesource (works on both Debian and Ubuntu)
        await self.exec_as_root(
            environment,
            "command -v node >/dev/null 2>&1 || ("
            "curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && "
            "apt-get install -y -qq nodejs"
            ")",
        )

        # Claude Code CLI (required by claude-agent-sdk)
        await self.exec_as_agent(environment, "npm install -g @anthropic-ai/claude-code")

        # Clone Buddy and install packages — no DB package, sandbox runs without DB
        await self.exec_as_agent(environment, f"git clone {REPO_URL} /opt/buddy")
        await self.exec_as_agent(
            environment,
            "pip3 install --break-system-packages /opt/buddy/sandbox /opt/buddy/autofyn",
        )

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        """Start sandbox server and run the headless orchestrator."""
        token_var = "$CLAUDE_CODE_OAUTH_TOKEN" if "CLAUDE_CODE_OAUTH_TOKEN" in __import__("os").environ else "$ANTHROPIC_API_KEY"
        sandbox_start_cmd = (
            f"AGENT_INTERNAL_SECRET={BENCH_SECRET} "
            f"CLAUDE_CODE_OAUTH_TOKEN={token_var} "
            "python3 -m sandbox.server &"
        )
        await self.exec_as_agent(environment, sandbox_start_cmd)

        # Wait for sandbox to become healthy
        await self._wait_for_sandbox(environment)

        cwd = await self._resolve_cwd(environment)

        run_cmd = (
            f"AGENT_INTERNAL_SECRET={BENCH_SECRET} "
            f"CLAUDE_CODE_OAUTH_TOKEN={token_var} "
            f"python3 -m headless {shlex.quote(instruction)} "
            f"--sandbox-url {SANDBOX_URL} "
            f"--cwd {shlex.quote(cwd)}"
        )
        result = await self.exec_as_agent(environment, run_cmd)
        context.add_step(result)

    def populate_context_post_run(self, context: AgentContext) -> None:
        pass

    async def _wait_for_sandbox(self, environment: BaseEnvironment) -> None:
        """Poll sandbox /health until ready."""
        for _ in range(HEALTH_POLL_ATTEMPTS):
            result = await self.exec_as_agent(
                environment,
                f"curl -sf {SANDBOX_URL}/health && echo ok || echo fail",
            )
            if "ok" in result:
                return
            await asyncio.sleep(HEALTH_POLL_INTERVAL_SEC)
        raise TimeoutError("Sandbox did not become healthy in time")

    async def _resolve_cwd(self, environment: BaseEnvironment) -> str:
        """Return the task working directory (prefer /root if it exists)."""
        result = await self.exec_as_agent(environment, "pwd")
        return result.strip() if result.strip() else "/root"
