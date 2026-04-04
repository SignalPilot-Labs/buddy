#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BUDDY_REPO_URL="https://github.com/SignalPilot-Labs/buddy.git"
BUDDY_HOME="$HOME/.buddy"
BUDDY_VENV="$BUDDY_HOME/.venv"
BUDDY_BIN="$HOME/.local/bin/buddy"
MIN_PYTHON_MINOR=12

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_ok()    { printf "[ok] %s\n" "$1"; }
_error() { printf "[error] %s\n" "$1" >&2; }
_info()  { printf "[buddy] %s\n" "$1"; }

_python3_minor() {
    python3 -c "import sys; print(sys.version_info.minor)"
}

# ---------------------------------------------------------------------------
# 1. Prerequisite checks
# ---------------------------------------------------------------------------
check_prereqs() {
    local missing=0

    if command -v git >/dev/null 2>&1; then
        _ok "git found: $(git --version)"
    else
        _error "git not found — install with: https://git-scm.com/downloads"
        missing=1
    fi

    if command -v docker >/dev/null 2>&1; then
        _ok "docker found: $(docker --version)"
        if ! docker info >/dev/null 2>&1; then
            _error "docker is installed but daemon is not running — start Docker and try again"
            missing=1
        fi
    else
        _error "docker not found — install with: https://docs.docker.com/get-docker/"
        missing=1
    fi

    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        _ok "docker compose plugin found"
    else
        _error "docker compose plugin not found — install with: https://docs.docker.com/compose/install/"
        missing=1
    fi

    if command -v python3 >/dev/null 2>&1; then
        local minor
        minor="$(_python3_minor)"
        if [ "$minor" -ge "$MIN_PYTHON_MINOR" ]; then
            _ok "python3 found: $(python3 --version)"
        else
            _error "python3.${MIN_PYTHON_MINOR}+ required, found 3.${minor} — install with: https://www.python.org/downloads/"
            missing=1
        fi
    else
        _error "python3 not found — install with: https://www.python.org/downloads/"
        missing=1
    fi

    if [ "$missing" -ne 0 ]; then
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# 2. Clone or update the repo
# ---------------------------------------------------------------------------
clone_or_update() {
    if [ -d "$BUDDY_HOME" ]; then
        if git -C "$BUDDY_HOME" rev-parse --git-dir >/dev/null 2>&1; then
            _info "Updating existing installation at $BUDDY_HOME"
            git -C "$BUDDY_HOME" pull
        else
            _error "$BUDDY_HOME exists but is not a git repository."
            _error "This looks like an old cp-based install. Remove it and re-run:"
            _error "  rm -rf $BUDDY_HOME && curl -fsSL https://get.buddy.sh | sh"
            exit 1
        fi
    else
        _info "Cloning Buddy to $BUDDY_HOME"
        git clone "$BUDDY_REPO_URL" "$BUDDY_HOME"
    fi
}

# ---------------------------------------------------------------------------
# 3. Create venv and install CLI
# ---------------------------------------------------------------------------
setup_venv() {
    if [ ! -d "$BUDDY_VENV" ]; then
        _info "Creating virtual environment at $BUDDY_VENV"
        python3 -m venv "$BUDDY_VENV"
    else
        _ok "Virtual environment already exists at $BUDDY_VENV"
    fi
    _info "Installing Buddy CLI into venv"
    "$BUDDY_VENV/bin/pip" install -e "$BUDDY_HOME/cli/" --quiet
}

# ---------------------------------------------------------------------------
# 4. Install wrapper shim to ~/.local/bin/buddy
# ---------------------------------------------------------------------------
install_wrapper() {
    mkdir -p "$(dirname "$BUDDY_BIN")"
    cat > "$BUDDY_BIN" <<'SHIM'
#!/usr/bin/env sh
exec "$HOME/.buddy/.venv/bin/buddy" "$@"
SHIM
    chmod +x "$BUDDY_BIN"
    _ok "Installed wrapper shim at $BUDDY_BIN"

    case ":${PATH}:" in
        *":$HOME/.local/bin:"*)
            ;;
        *)
            _info "~/.local/bin is not on your PATH."
            _info "Add this to your shell rc file (~/.bashrc, ~/.zshrc, etc.):"
            _info "  export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
    esac
}

# ---------------------------------------------------------------------------
# 5. Build Docker images
# ---------------------------------------------------------------------------
build_images() {
    _info "Building Docker images (this may take a while)..."
    bash "$BUDDY_HOME/cli/scripts/build.sh"
}

# ---------------------------------------------------------------------------
# 6. Start services
# ---------------------------------------------------------------------------
start_services() {
    _info "Starting Buddy services..."
    bash "$BUDDY_HOME/cli/scripts/up.sh"
}

# ---------------------------------------------------------------------------
# 7. Prompt for credentials and persist via CLI
# ---------------------------------------------------------------------------
prompt_credentials() {
    if [ ! -t 0 ] && { [ -z "${ANTHROPIC_API_KEY:-}" ] || [ -z "${GITHUB_TOKEN:-}" ] || [ -z "${GITHUB_REPO:-}" ]; }; then
        _error "stdin is not a terminal and credentials are not set via env vars."
        _error "Set ANTHROPIC_API_KEY, GITHUB_TOKEN, and GITHUB_REPO before piping to sh."
        exit 1
    fi

    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        printf "Anthropic API key: "
        read -r ANTHROPIC_API_KEY < /dev/tty
        if [ -z "$ANTHROPIC_API_KEY" ]; then
            _error "Anthropic API key cannot be empty."
            exit 1
        fi
    else
        _ok "ANTHROPIC_API_KEY already set, skipping prompt"
    fi

    if [ -z "${GITHUB_TOKEN:-}" ]; then
        printf "GitHub token: "
        read -r GITHUB_TOKEN < /dev/tty
        if [ -z "$GITHUB_TOKEN" ]; then
            _error "GitHub token cannot be empty."
            exit 1
        fi
    else
        _ok "GITHUB_TOKEN already set, skipping prompt"
    fi

    if [ -z "${GITHUB_REPO:-}" ]; then
        printf "GitHub repo (owner/repo): "
        read -r GITHUB_REPO < /dev/tty
        if [ -z "$GITHUB_REPO" ]; then
            _error "GitHub repo cannot be empty."
            exit 1
        fi
    else
        _ok "GITHUB_REPO already set, skipping prompt"
    fi

    "$BUDDY_VENV/bin/buddy" settings set \
        --claude-token "$ANTHROPIC_API_KEY" \
        --git-token "$GITHUB_TOKEN" \
        --github-repo "$GITHUB_REPO"
}

# ---------------------------------------------------------------------------
# 8. Success message
# ---------------------------------------------------------------------------
print_success() {
    printf "\n"
    _ok "Buddy is running. Open the dashboard at: http://localhost:3400"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
check_prereqs
clone_or_update
setup_venv
install_wrapper
build_images
start_services
prompt_credentials
print_success
