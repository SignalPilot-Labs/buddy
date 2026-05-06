# Safety & Security

## Threat Model

- **Operator** is trusted — owns machine, SSH keys, tokens.
- **Threats:** other HPC users on shared nodes, subagents escaping sandbox, credential leakage.

## Authentication

All inter-service communication is authenticated with 256-bit secrets via headers:

- **Sandbox:** `X-Internal-Secret` on every endpoint (except `/health`, `/heartbeat`)
- **Agent:** `AGENT_INTERNAL_SECRET` header from dashboard
- **Connector:** `CONNECTOR_SECRET` header from dashboard

Only `/health` (returns status) and `/heartbeat` (returns `{"ok": true}`) are unauthenticated.

## Remote Sandbox

- Secrets passed via SSH stdin (`bash -s`) — never in cmdline or `/proc/<pid>/cmdline`
- Sandbox generates its own auth secret at startup, transmits via encrypted SSH stdout
- Git tokens injected post-startup via authenticated `POST /env`
- Port 8923 — other users can see it's open but cannot authenticate

## SecurityGate

Blocks subagents from:

- Referencing secret env vars (`GIT_TOKEN`, `ANTHROPIC_API_KEY`, etc.)
- Reading `/proc/<pid>/environ`
- Network exfiltration to external hosts
- Git destructive ops (force-push, branch delete, `git clean`)
- GitHub API writes (orchestrator-only)

## Local Docker

- Isolated Docker network, port not published to host
- gVisor syscall filtering when enabled
- Each run gets own container + repo volume
