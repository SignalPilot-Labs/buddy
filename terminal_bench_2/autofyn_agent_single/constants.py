"""Constants for the Terminal-Bench AutoFyn adapter."""

from pathlib import Path

# Working directory inside the task container
TASK_CWD: str = "/app"

# Models — overridable via AUTOFYN_MODEL / AUTOFYN_FALLBACK_MODEL env vars
DEFAULT_MODEL: str = "claude-opus-4-6"
DEFAULT_FALLBACK_MODEL: str = "claude-sonnet-4-6"

# Paths
PROMPTS_DIR: Path = Path(__file__).parent / "prompts"
SUBAGENTS_DIR: Path = PROMPTS_DIR / "subagents"

# Claude plugins
CLAUDE_PLUGINS_JSON: Path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
CAVEMAN_PLUGIN_KEY: str = "caveman@caveman"
CAVEMAN_SKILL_RELATIVE: str = "caveman/SKILL.md"

# Subagent timeout — block tool use after this many seconds idle
SUBAGENT_TIMEOUT_SEC: int = 10 * 60

# Truncation limit for tool input/output in JSONL
INPUT_SUMMARY_MAX_LEN: int = 500

# Max agent turns per task
DEFAULT_MAX_TURNS: int = 30

# Env var opt-in for single-session mode (bypass multi-subagent orchestration)
# Set AUTOFYN_SINGLE_SESSION=1 to route the task through a single combined prompt
# instead of the planner->builder->reviewer subagent loop.
SINGLE_SESSION_ENV_VAR: str = "AUTOFYN_SINGLE_SESSION"
