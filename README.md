# Buddy

Autonomous coding agent powered by the Claude Agent SDK. Runs Claude in a planner/builder/reviewer loop, makes commits to a GitHub repo, and opens PRs — supervised via a real-time monitor UI.

## Quick Start

```bash
# 1. Copy .env and fill in tokens
cp buddy/.env.example .env
# Required: GIT_TOKEN, CLAUDE_CODE_OAUTH_TOKEN, GITHUB_REPO

# 2. Start the buddy stack (monitor UI + audit DB + agent)
cd buddy
docker compose up --build -d

# 3. (Optional) Start the sandbox for safe code execution
cd ../sandbox
docker compose up --build -d
```

**URLs after startup:**

| Service | URL | Description |
|---------|-----|-------------|
| Monitor UI | http://localhost:3400 | Agent run feed, controls (pause/stop/inject), cost tracking |
| Monitor API | http://localhost:3401 | SSE event stream, run history, control signals |
| Sandbox Manager | http://localhost:8080 | Firecracker/gVisor code execution |

---

## Architecture

```
        Browser
           |
      localhost:3400
      Monitor Web
      (Next.js 16)
           |
      localhost:3401
      Monitor API
      (FastAPI)
           |
     +-----+-----+
     |           |
   Audit DB    Agent
   (SQLite)   (Claude SDK)
                 |
            Sandbox :8080
            (Firecracker/gVisor)
```

---

## Components

### `buddy/` — Autonomous Agent

The core agent loop and its monitor:

- **core/** — Agent loop, bootstrap, stream processing, teardown, event bus
- **tools/** — SDK hooks: security gate, session gate, DB logger
- **utils/** — Constants, DB, git, prompts, models, helpers
- **dashboard/** — FastAPI backend + Next.js frontend: real-time SSE feed, run list, control bar
- **prompts/** — Markdown prompt templates (system, planner, subagents)

#### Planner/Worker Loop

When a run has a duration lock (e.g. 4 hours):

1. **Worker** executes: calls builder/reviewer subagents, runs git, commits
2. **Planner** reviews round context, decides the next step
3. Repeat until time expires or operator sends `unlock`

Without a duration lock, it's single-shot: one round, then done.

### `sandbox/` — Sandbox Manager

Safe code execution with auto-detecting backend:

- **Linux (KVM):** Firecracker microVMs (~200ms)
- **macOS / no KVM:** gVisor user-space kernel (~230ms)

Same `POST /execute` API regardless of backend.


---

## Monitor API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/runs` | List all runs |
| GET | `/api/runs/{id}` | Run details (cost, tokens, status) |
| GET | `/api/runs/{id}/tools` | Tool call history |
| GET | `/api/runs/{id}/audit` | Audit event log |
| POST | `/api/runs/{id}/pause` | Pause agent |
| POST | `/api/runs/{id}/resume` | Resume agent |
| POST | `/api/runs/{id}/inject` | Inject prompt into running agent |
| POST | `/api/runs/{id}/stop` | Graceful stop (agent commits + creates PR) |
| POST | `/api/runs/{id}/unlock` | End time-lock after current round |
| POST | `/api/agent/start` | Start new run |
| POST | `/api/agent/stop` | Graceful stop via in-process queue |
| POST | `/api/agent/kill` | Immediate cancel |
| GET | `/api/agent/health` | Agent container status |
| GET | `/api/stream/{id}` | SSE real-time event stream |
