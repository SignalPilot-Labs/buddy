"""All magic values for the agent package."""

from pathlib import Path

# ── Subagent Timeouts ──
SUBAGENT_TIMEOUT_SEC = 45 * 60       # 45 min — absolute timeout (block tool calls)
SUBAGENT_IDLE_KILL_SEC = 10 * 60     # 10 min idle — trigger interrupt+recovery
PULSE_CHECK_INTERVAL_SEC = 30

# ── Run Limits ──
MAX_ROUNDS = 500
MAX_BUDGET_DEFAULT = 50.0

# ── Serialization Limits ──
MAX_STR_LEN = 5000
MAX_LIST_LEN = 100

# ── Truncation Limits (audit/logging) ──
AUDIT_TEXT_LIMIT = 2000
PROMPT_SUMMARY_LIMIT = 200
TEXT_CHUNK_LIMIT = 500
ROUND_SUMMARY_LIMIT = 1500
ASSIGNMENT_LIMIT = 1000
INPUT_SUMMARY_LIMIT = 500
TRANSCRIPT_LIMIT = 3000
FINAL_TEXT_LIMIT = 2000
LOG_PREVIEW_LIMIT = 200
FILES_CHANGED_LIMIT = 500
ROUND_SUMMARY_AUDIT_LIMIT = 500

# ── Paths ──
WORK_DIR = "/home/agentuser/repo"
WORKSPACE_DIR = "/workspace"
SKILLS_SRC_PATH = "/workspace/buddy/skills"
SKILLS_FALLBACK_PATH = Path(__file__).parent.parent / "skills"
PROMPTS_DIR = Path("/workspace/buddy/prompts")
PROMPTS_FALLBACK_DIR = Path(__file__).parent.parent / "prompts"
ALLOWED_PATHS = ("/workspace", "/home/agentuser/repo", "/tmp")
ALLOWED_SYSTEM_PATHS = ("/tmp", "/usr", "/var", "/etc/apt")

# ── Git ──
CLONE_DEPTH = 50
CLONE_TIMEOUT = 300
CMD_TIMEOUT = 120
PROTECTED_BRANCHES = frozenset({"main", "master", "staging", "prod", "production"})
BRANCH_NAME_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$'
BRANCH_NAME_MAX_LEN = 256

# ── Security Patterns ──
CREDENTIAL_PATTERNS = [
    r"\.env($|\.|/)",
    r"credentials",
    r"\.pem$",
    r"\.key$",
    r"secret",
    r"\.token$",
    r"id_rsa",
    r"id_ed25519",
    r"\.gnupg",
    r"\.ssh/",
    r"\.npmrc$",
    r"\.pypirc$",
    r"\.docker/config\.json",
]

DANGEROUS_PATTERNS = [
    r"rm\s+(-\w*r\w*f|--force.*--recursive|--recursive.*--force)\s+/\s*$",
    r"mkfs\.",
    r"dd\s+.*of=/dev/",
    r">\s*/dev/sd[a-z]",
    r"chmod\s+-R\s+777\s+/\s*$",
]

SECRET_ENV_VARS = "GIT_TOKEN|ANTHROPIC_API_KEY|GH_TOKEN|CLAUDE_CODE_OAUTH_TOKEN|FGAT_GIT_TOKEN"

# ── Server ──
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8500
STARTUP_WAIT_SEC = 2
KILL_WAIT_SEC = 0.5
