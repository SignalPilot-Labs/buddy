# Safety & Security

How AutoFyn protects secrets, isolates execution, and secures remote sandboxes.

## Threat Model

- **Operator (user)** is trusted — they own the machine, SSH keys, and tokens.
- **Threats:** other HPC users on shared nodes, subagents escaping the sandbox, credential leakage via process metadata.
- **Not threats:** root-level attackers, compromised Slurm admins, kernel exploits.

## Authentication

### Sandbox ↔ Agent

Every sandbox HTTP endpoint (except `/health` and `/heartbeat`) requires a 256-bit secret in the `X-Internal-Secret` header. Requests without a valid secret get `401 Unauthorized`.

- **Local Docker:** secret is set in docker-compose, shared between agent and sandbox via env var.
- **Remote sandboxes:** sandbox generates its own secret at startup (`secrets.token_hex(32)`) and transmits it in the `AF_READY` marker over the encrypted SSH stdout pipe. The secret never appears in command-line arguments, Slurm job metadata, or process environment visible to other users.

### Agent ↔ Dashboard

Dashboard authenticates to the agent via `AGENT_INTERNAL_SECRET` (same pattern — header-based auth on all endpoints).

### Connector ↔ Dashboard

Connector authenticates via `CONNECTOR_SECRET` header.

## Remote Sandbox Security

### Secrets never in SSH cmdline

All environment variables (mount configs, run keys, timeouts) are passed via SSH stdin using `bash -s`. This prevents exposure via `ps aux` or `/proc/<pid>/cmdline` on shared systems.

### Port binding

The sandbox binds to `0.0.0.0` on port 8923 (configurable via `AF_SANDBOX_PORT`). Other users on the same compute node can see the port is open but cannot authenticate — every request requires the 256-bit secret.

### SSH tunnel

Traffic between the connector and remote sandbox flows through an SSH tunnel (`ssh -L`). The tunnel terminates on the login node and forwards to the compute node. The HTTP layer is unencrypted between login and compute node (cluster-internal network), but the auth secret prevents unauthorized access even if traffic is sniffed — an attacker would need to capture the secret from the initial AF_READY marker (which flows over encrypted SSH stdout, not the tunnel).

### Unauthenticated endpoints

| Endpoint | Exposed info | Risk |
|----------|-------------|------|
| `/health` | `{"status": "healthy", "active_sessions": 0, "protocol_version": ..., "image_tag": ...}` | None — confirms something is running (port scan already reveals this) |
| `/heartbeat` | `{"ok": true}` | None |

## SecurityGate (Subagent Sandboxing)

The SecurityGate blocks subagents from:

1. **Secret env var references** — commands mentioning `GIT_TOKEN`, `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, `FGAT_GIT_TOKEN`, `SANDBOX_INTERNAL_SECRET`, `AGENT_INTERNAL_SECRET`, `GH_TOKEN` are blocked.
2. **`/proc/<pid>/environ` reads** — blocks secret exfiltration via procfs.
3. **Network exfiltration** — blocks curl/wget/fetch to external hosts (except allowed domains).
4. **Git destructive ops** — blocks force-push, branch deletion, `git clean`.
5. **GitHub API writes** — orchestrator owns PR/release/repo operations.

## Local Docker Isolation

- Sandbox containers run on an isolated Docker network. Port is not published to the host.
- gVisor (runsc) provides kernel-level syscall filtering when enabled.
- Each run gets its own container and repo volume — no cross-run contamination.

## Credential Lifecycle

1. Secrets are generated or loaded at startup and immediately removed from `os.environ` (popped).
2. Git tokens are injected post-startup via authenticated `POST /env` — never in the start command.
3. The SecurityGate prevents subagents from reading secrets via env, procfs, or shell expansion.
