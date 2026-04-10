# AutoFyn

Autonomous AI software engineer. Runs as a Docker stack: agent container (Claude Code SDK), dashboard (FastAPI + Next.js), PostgreSQL, sandbox (gVisor).

## How It Works

Three containers: `autofyn/` is the brain (orchestrator, decisions, DB), `sandbox/` is the hands (executes all code, git, Claude SDK), `dashboard/` is the control plane (starts/stops runs, settings, SSE streaming). Agent never runs untrusted code — everything goes through HTTP to sandbox.

The orchestrator delegates to subagents (planner, builder, reviewer, explorer, frontend-builder). Planner writes specs to `/tmp/current-spec.md`, builders read and implement, reviewer writes findings to `/tmp/current-review.md`. Subagents communicate through these shared files.

## Package Layout

- `autofyn/` — Agent (brain): orchestrator loop, stream processor, subagent prompts, sandbox_manager client
- `autofyn/sandbox_manager/` — HTTP client to sandbox: repo ops, deps installer, session management
- `sandbox/` — Sandbox (hands): command execution, Claude SDK sessions, SecurityGate, gVisor
- `sandbox/executor/` — gVisor and Firecracker code execution backends
- `sandbox/session/` — Claude SDK session lifecycle and security gating
- `dashboard/backend/` — FastAPI dashboard API: runs, settings, SSE streaming, agent proxy
- `dashboard/frontend/` — Next.js UI: run feed, controls, settings, diff viewer
- `db/` — Shared SQLAlchemy models and connection (PostgreSQL)
- `cli/` — CLI tool: `autofyn start/stop/run/settings` via dashboard API

## Tech Stack

- Python 3.12, FastAPI, SQLAlchemy (async), Claude Agent SDK
- Next.js 15, TypeScript, Tailwind CSS, Framer Motion
- PostgreSQL, Docker Compose, gVisor

---

# Code Rules

These rules are mandatory. All AI agents (planner, builder, reviewer, etc.) must follow them. No exceptions.

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
