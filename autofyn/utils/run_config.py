"""Per-run agent configuration resolved after the target repo is cloned.

`RunAgentConfig` is a frozen dataclass holding the 4 per-run values that
can be overridden by the target repo's `.autofyn/config.yml`. It is
created once per run during bootstrap (after sandbox.repo.bootstrap())
and threaded through the lifecycle via BootstrapResult.

The target repo config is read from the sandbox container via HTTP — not
from the agent's local filesystem — because the repo lives in the sandbox.
"""

from dataclasses import dataclass

import yaml

from config.loader import deep_merge, load
from sandbox_client.client import SandboxClient
from utils.constants import WORK_DIR

_AUTOFYN_CONFIG_PATH = f"{WORK_DIR}/.autofyn/config.yml"


@dataclass(frozen=True)
class RunAgentConfig:
    """Immutable per-run agent configuration resolved after clone."""

    max_rounds: int
    tool_call_timeout_sec: int
    session_idle_timeout_sec: int
    subagent_idle_kill_sec: int


async def load_run_agent_config(sandbox: SandboxClient) -> RunAgentConfig:
    """Read target-repo config from sandbox, merge with base, build RunAgentConfig.

    Resolution order:
      1. Base config from config.loader.load(None) (defaults + global + project + env)
      2. Target repo's .autofyn/config.yml agent section (if it exists)

    The target repo config is untrusted user input — parsed with yaml.safe_load.
    If the file is missing or has no `agent` section, base config is used as-is.
    """
    base_config = load(None)
    content = await sandbox.file_system.read(_AUTOFYN_CONFIG_PATH)
    if content is not None:
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict) and "agent" in parsed:
            base_config = deep_merge(base_config, {"agent": parsed["agent"]})

    agent = base_config["agent"]
    return RunAgentConfig(
        max_rounds=agent["max_rounds"],
        tool_call_timeout_sec=agent["tool_call_timeout_sec"],
        session_idle_timeout_sec=agent["session_idle_timeout_sec"],
        subagent_idle_kill_sec=agent["subagent_idle_kill_sec"],
    )
