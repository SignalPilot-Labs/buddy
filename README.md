# Buddy by SignalPilot

Autonomous coding agent powered by the Claude Agent SDK. Runs Claude in a timed CEO/Worker loop, makes commits to a GitHub repo, and opens PRs — supervised via a real-time monitor UI.

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

- **agent/** — Claude Agent SDK runner with CEO/Worker loop, git ops, permissions, audit hooks
- **monitor/** — FastAPI backend: runs, tool calls, control signals (pause/resume/inject/stop)
- **monitor-web/** — Next.js dashboard: real-time SSE feed, run list, control bar
- **prompts/** — Markdown prompt templates (system, CEO, continuation, session gate)

#### CEO/Worker Loop

When a run has a duration lock (e.g. 4 hours):

1. **Worker** executes the assigned task, then stops
2. **CEO (Product Director)** reviews what was done, sees the original prompt, assigns the next task
3. Repeat until time expires or operator sends `unlock`

Without a duration lock, it's single-shot: one round, then done.

### `sandbox/` — Sandbox Manager

Safe code execution with auto-detecting backend:

- **Linux (KVM):** Firecracker microVMs (~200ms)
- **macOS / no KVM:** gVisor user-space kernel (~230ms)

Same `POST /execute` API regardless of backend.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GIT_TOKEN` | Yes | GitHub PAT with repo scope |
| `CLAUDE_CODE_OAUTH_TOKEN` | Yes | Claude Code OAuth token |
| `GITHUB_REPO` | Yes | Target repo slug (e.g. `SignalPilot-Labs/buddy`) |
| `MAX_BUDGET_USD` | No | Max budget per agent run, 0 = unlimited (default: `0`) |

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
