# AutoFyn

Autonomous AI software engineer. Runs as a Docker stack: agent container (Claude Code SDK), dashboard (FastAPI + Next.js), PostgreSQL, sandbox (gVisor).

## How It Works

Three containers: `autofyn/` is the brain (orchestrator, decisions, DB), `sandbox/` is the hands (executes all code, git, Claude SDK), `dashboard/` is the control plane (starts/stops runs, settings, SSE streaming). Agent never runs untrusted code — everything goes through HTTP to sandbox.

The orchestrator delegates to subagents organized by phase: Explore (code-explorer, debugger), Plan (architect), Build (backend-dev, frontend-dev), Review (code-reviewer, ui-reviewer, security-reviewer). Subagents write their reports to `/tmp/round-N/<agent-name>.md`.

## Package Layout

- `autofyn/` — Agent (brain): orchestrator loop, lifecycle, memory, session, subagent prompts
- `autofyn/sandbox_client/` — HTTP client to sandbox: repo ops, session management, file I/O
- `sandbox/` — Sandbox (hands): HTTP API, command execution, Claude SDK sessions, SecurityGate
- `sandbox/handlers/` — HTTP endpoints: execute, file_system, repo, session, health
- `sandbox/session/` — Claude SDK session lifecycle and security gating
- `dashboard/backend/` — FastAPI dashboard API: runs, settings, SSE streaming, agent proxy
- `dashboard/frontend/` — Next.js UI: run feed, controls, settings, diff viewer
- `db/` — Shared SQLAlchemy models and connection (PostgreSQL)
- `cli/` — CLI tool: `autofyn start/stop/run/settings` via dashboard API

## Tech Stack

- Python 3.12, FastAPI, aiohttp, SQLAlchemy (async), Claude Agent SDK
- Next.js 15, TypeScript, Tailwind CSS, Framer Motion
- PostgreSQL, Docker Compose, gVisor

## Build & Install — IMPORTANT

**This is a monorepo. There is NO installable root package. Do NOT run `pip install -e .` at the repo root — it will fail.**

The root `pyproject.toml` is pytest config only. No `[build-system]`, no `[project]`. Running `pip install -e .` or `pip install -e autofyn/` from the repo root will error with `"not a valid editable requirement"` or `"Getting requirements to build editable did not run successfully"`.

**There are no Python deps to install on the host.** All Python packages live inside Docker containers and are installed by the Dockerfiles via `uv pip install --system --no-cache "/app/[dev]"` (or equivalent) at image build time. The agent, sandbox, and dashboard all run inside containers that already have their deps. Host-side tests do not need an editable install — pytest's `pythonpath` in the root `pyproject.toml` (`["autofyn", "dashboard", "sandbox", "db", "."]`) resolves imports for local development.

**If you're a subagent told to "set up the build environment"** (per the Round 1 instructions): check for `package.json` and run `npm ci` only in those directories that have one. For Python, there is nothing to install — skip it. Do NOT run `pip install -e .` or `pip install -e autofyn/` at the root.

The actual Python packages live in subdirectories, each with their own `pyproject.toml`:

- `autofyn/pyproject.toml` — agent orchestrator (installed in `autofyn-agent` container)
- `sandbox/pyproject.toml` — sandbox HTTP server (installed in `autofyn-sandbox` container)
- `cli/pyproject.toml` — `autofyn` CLI (installed on the host by `install.sh`)
- `dashboard/backend/pyproject.toml` — dashboard FastAPI backend (installed in `autofyn-dashboard` container)
- `db/pyproject.toml` — shared SQLAlchemy models (installed in all three containers)

Day-to-day development runs everything via `docker compose up -d` (or `autofyn start`). To rebuild a container after a code change: `docker compose build <service> && docker compose up -d --force-recreate <service>`.

---

# Code Rules

These rules are mandatory. All AI agents must follow them. No exceptions.

## Imports

- All imports at the top of the file. No inline imports inside functions or methods.
- Absolute imports from the package root. No relative imports (`from . import`). No `sys.path` hacks.
- `__init__.py` files must be empty. No code, no re-exports, no `__all__`.

## Constants

- All magic values (numbers, strings, URLs, ports, timeouts, limits) go in a dedicated `constants.py`, `models.py` or `sh` file.
- No magic values inline in code. No default values for function parameters — pass constants explicitly at the call site.

## Types

- Every function must have full type annotations (parameters and return type).
- Run `pyright` before considering work done. It must pass at `standard` level (configured in `pyrightconfig.json`).

## No Defensive Coding

- No `hasattr()`, `isinstance()` checks for duck typing, `getattr()` with defaults, or `try/except` for control flow.
- Trust your types. If the type system says it's there, it's there. If it might not be, fix the type.

## Fail Fast

- Never mask a failure with a fallback. If a required value is missing, raise/reject — do not substitute a default and keep going.
- No layered `value ?? fallback1 ?? fallback2 ?? default` chains that hide which layer is broken. One source of truth, one failure surface.
- Dead fallback parameters lie about the contract. If a parameter is only used when the real source is null, drop it.
- Silent error swallowing (empty `catch`, `try/except: pass`, fallback to stale state) is worse than a crash. Surface the error and let the caller decide.
- Distinct failure modes must render/report distinctly. `$0.00` shown for "no data yet", "really zero", and "pipeline broken" hides bugs; render `—` for missing and `$0.00` only when confirmed.

## Architecture

- OOP with clear separation of concerns. One class, one responsibility. One function, one task.
- Orchestrator/executor pattern: orchestrators delegate, executors do work. No god classes.
- Dependency injection: pass dependencies in, don't import and instantiate internally.
- DRY: if logic appears twice, extract it. Common code in base classes or shared helpers.

## Size Limits

- No function longer than 50 lines except in critical cases. Extract helpers.
- No file longer than 400 lines. Split into focused modules.

## Tests

- One test class per file. Test files share fixtures, mocks, and conftest helpers — but each class lives in its own file.

## Verification

Before finishing any task, run:
```
pyright
ruff check
```
Both must pass clean.

## Pull Requests

- **Always open PRs against `main`.** The repo default branch is `production`, but that is the release branch — day-to-day work merges into `main`. Pass `--base main` explicitly to `gh pr create` (or edit the base after creation) so PRs don't land on `production` by accident.
