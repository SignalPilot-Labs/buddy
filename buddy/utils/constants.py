"""All magic values for the agent package."""

from pathlib import Path

# ── Subagent Timeouts ──
SUBAGENT_TIMEOUT_SEC = 45 * 60       # 45 min — absolute timeout (block tool calls)
SUBAGENT_IDLE_KILL_SEC = 10 * 60     # 10 min idle — trigger interrupt+recovery
PULSE_CHECK_INTERVAL_SEC = 30

# ── Run Limits ──
MAX_ROUNDS = 500
MAX_BUDGET_DEFAULT = 50.0
RATE_LIMIT_MAX_WAIT_SEC = 600      # Max seconds to wait for rate limit reset before stopping

# ── Serialization Limits ──
MAX_STR_LEN = 5000
MAX_LIST_LEN = 100

# ── Truncation Limits (audit/logging) ──
# These protect the DB and logs from unbounded text.
# Each limit is tuned for its context: previews are short, full text is longer.
AUDIT_TEXT_LIMIT = 2000            # LLM text/thinking deltas stored in audit log
PROMPT_SUMMARY_LIMIT = 200         # Custom prompt preview in API responses and audit
TEXT_CHUNK_LIMIT = 500             # Per-round text chunks collected for planner context
ROUND_SUMMARY_LIMIT = 1500        # Combined round text sent to planner prompt
ASSIGNMENT_LIMIT = 1000           # Tool assignment descriptions in logs
INPUT_SUMMARY_LIMIT = 500         # Tool input summaries in security audit
TRANSCRIPT_LIMIT = 3000           # Subagent transcript final text extraction
FINAL_TEXT_LIMIT = 2000           # Subagent completion text stored in audit
LOG_PREVIEW_LIMIT = 200           # One-line log preview of assistant messages
FILES_CHANGED_LIMIT = 500         # Git files-changed list in planner audit meta
ROUND_SUMMARY_AUDIT_LIMIT = 500   # Round summary stored in planner audit meta

# ── Paths ──
WORK_DIR = "/home/agentuser/repo"
WORKSPACE_DIR = "/workspace"
RESEARCH_DIR = "/home/agentuser/research"
SKILLS_SRC_PATH = f"{WORKSPACE_DIR}/buddy/skills"
SKILLS_FALLBACK_PATH = Path(__file__).parent.parent / "skills"
PROMPTS_DIR = Path(f"{WORKSPACE_DIR}/buddy/prompts")
PROMPTS_FALLBACK_DIR = Path(__file__).parent.parent / "prompts"
ALLOWED_PATHS = (WORKSPACE_DIR, WORK_DIR, "/tmp")
ALLOWED_SYSTEM_PATHS = ("/tmp", "/usr", "/var", "/etc/apt")

# ── Git ──
CLONE_DEPTH = 50
CLONE_TIMEOUT = 300
CMD_TIMEOUT = 120
NPM_INSTALL_TIMEOUT = 300
BRANCH_NAME_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$'
BRANCH_NAME_MAX_LEN = 256
GIT_RETRY_ATTEMPTS = 3
GIT_RETRY_DELAY_SEC = 2.0
RATE_LIMIT_SLEEP_BUFFER_SEC = 5

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

# ── Input Limits ──
INJECT_PAYLOAD_MAX_LEN = 50000
MAX_OPERATOR_MESSAGES = 25

# ── Server ──
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8500
KILL_WAIT_SEC = 0.5
EVENT_BUS_POLL_TIMEOUT_SEC = 2.0
RATE_LIMIT_POLL_INTERVAL_SEC = 10
DEFAULT_BASE_BRANCH = "main"

# ── Models ──
DEFAULT_AGENT_MODEL = "opus"
DEFAULT_FALLBACK_MODEL = "sonnet"
