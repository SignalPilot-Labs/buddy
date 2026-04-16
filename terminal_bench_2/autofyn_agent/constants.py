"""Constants for the Terminal-Bench AutoFyn adapter."""

from pathlib import Path

# Working directory inside the task container
TASK_CWD: str = "/app"

# Models — overridable via AUTOFYN_MODEL / AUTOFYN_FALLBACK_MODEL env vars
DEFAULT_MODEL: str = "claude-opus-4-6"
DEFAULT_FALLBACK_MODEL: str = "claude-sonnet-4-6"

# Claude binary name
DEFAULT_CLAUDE_BIN: str = "claude"

# Paths
PROMPTS_DIR: Path = Path(__file__).parent / "prompts"

# Truncation limit for tool input/output in JSONL
INPUT_SUMMARY_MAX_LEN: int = 500

# Subagent timeout — block tool use after this many seconds idle (used by hooks.py)
SUBAGENT_TIMEOUT_SEC: int = 10 * 60

# Max agent turns per task — single-session uses 1 turn per tool call
DEFAULT_MAX_TURNS: int = 75
