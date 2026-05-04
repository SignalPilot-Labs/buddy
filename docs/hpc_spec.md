# Remote Sandbox — Spec

## Summary

Run the per-run sandbox on a remote machine instead of local Docker. The agent, dashboard, and DB stay local. Only the sandbox moves.

## User flow

```
Terminal:   autofyn start                    # local stack: db, dashboard, agent, connector
Dashboard:  Settings → Remote Sandboxes → Add "Lab HPC"
Dashboard:  New Run → select repo → Sandbox: "Lab HPC" → Start
```

The user configures remote sandboxes once in settings, then picks one from a radio group when starting a run.

## Settings: Remote Sandboxes

Settings page gets a "Remote Sandboxes" section — same pattern as repos. Each remote sandbox is a named configuration:

```
Remote Sandboxes
┌──────────────────────────────────────────────────────────────┐
│  Name:           [Lab HPC                                  ] │
│  SSH Target:     [user@hpc.example.edu                  ] │
│  Type:           ● Slurm    ○ Docker                        │
│                                                              │
│  Default Start Command:                                      │
│  [module load apptainer/1.4.2 && srun --partition=gpu      ] │
│  [--gres=gpu:1 -n 4 --mem=16G -t 4:00:00 apptainer exec   ] │
│  [--nv ~/.autofyn/sandbox.sif python3 -m sandbox.server    ] │
│                                                              │
│  [Test Connection]                                  [Save]   │
└──────────────────────────────────────────────────────────────┘
```

- **Name** — user-chosen display label for the sandbox radio group. Must be unique. Internally, each config gets a stable UUID (`sandbox_id`) — all DB keys, run columns, and mount keys reference the UUID, not the name. Renaming a sandbox does not break active runs or orphan cleanup.
- **SSH Target** — passed straight to SSH. User's `~/.ssh/config` handles keys, jump hosts, ProxyJump, Kerberos. AutoFyn never touches SSH keys directly.
- **Type** — `slurm` or `docker`. Determines how AutoFyn stops the sandbox and retrieves logs (see "Derived stop and logs"). The user never provides stop or logs commands.
- **Default Start Command** — the start command pre-filled in the run modal. Contains module loads, scheduler flags, resource requests, image path — everything cluster-specific. Must emit structured ready markers on stdout (see "Startup protocol"). Users typically set this once and tweak per-run in the run modal.

**No stop or logs commands.** AutoFyn derives these from the type + backend handle:

| Type | Has `backend_id` | Stop |
|---|---|---|
| Slurm | yes (`sbatch`) | `scancel <backend_id>` |
| Slurm | no (`srun`) | kill the start SSH process (kills allocation) |
| Docker | yes (always) | `docker rm -f <backend_id>` |

For Slurm with `srun`, the start SSH process is the allocation — killing it is the stop. The connector keeps this process handle in `ForwardState`. For `sbatch`, the start process exits after emitting `AF_READY`, so stop must use `scancel`.

All stop paths are idempotent. Logs use the ring buffer — see "Sandbox logs."

### Run creation: sandbox picker + start command

When starting a run, the user sees a sandbox radio group and an editable start command:

```
SANDBOX
  ● Docker (local)
  ○ Lab HPC (Slurm)
  ○ Lab GPU Box (Docker)

┌─ Start Command ──────────────────────────────────────────────┐
│  module load apptainer/1.4.2 && srun --partition=gpu         │
│  --gres=gpu:1 -n 4 --mem=16G -t 4:00:00 apptainer exec      │
│  --nv ~/.autofyn/sandbox.sif python3 -m sandbox.server       │
└──────────────────────────────────────────────────────────────┘

HOST MOUNTS (REMOTE)
  ...
```

"Docker (local)" is always first and selected by default. Named remote sandboxes appear below with their type suffix. Start command is pre-filled from:
1. Last-used command for this repo+target (if any)
2. Default start command from settings (otherwise)

The user can tweak resource flags (GPU count, partition, time limit) before each run without going back to settings. Changes apply to this run only — the settings default is not modified.

The Host Mounts accordion label changes based on selection:
- Local selected → **LOCAL HOST MOUNTS**
- Remote selected → **REMOTE HOST MOUNTS**

This tells the user which filesystem the paths refer to — their laptop or the remote machine. The saved set swaps too (`local_mounts:{repo}` vs `remote_mounts:{repo}:{sandbox_id}`). Same UI, same position, just different label and backing store. The connector sets `AF_HOST_MOUNTS_JSON` (raw JSON) plus a pre-computed runtime-specific env var: `AF_APPTAINER_BINDS` (Slurm) or `AF_DOCKER_VOLUMES` (Docker). The start command uses the pre-computed var directly — no JSON parsing needed in shell.

Local and remote mounts are stored separately per repo (`local_mounts:{repo}` vs `remote_mounts:{repo}:{sandbox_id}`) so switching doesn't wipe either.

### Startup protocol

The start command's stdout is noisy — shell profiles, module load messages, Slurm banners, Apptainer warnings. Parsing "line 1 = host:port" is fragile.

The connector scans stdout for **structured markers** anywhere in the output. There are two markers, used in sequence:

**1. `AF_QUEUED` (optional) — immediate cancellation handle:**
```
AF_QUEUED {"backend_id":"12345"}
```
Emitted as soon as the wrapper has a handle to cancel the job (e.g. Slurm job ID from `sbatch` output). The connector streams this as a `queued` NDJSON event to the agent, which immediately persists `backend_id` to the runs table. This enables orphan cleanup to cancel queued jobs even if the sandbox never starts.

For non-queued backends (direct Apptainer, Docker), skip this marker entirely.

**2. `AF_READY` (required) — sandbox is up:**
```
AF_READY {"host":"compute-7","port":9123}
```
Optional fields: `"backend_id":"autofyn-abc123"` (for backends that don't emit `AF_QUEUED` — e.g. Docker container name, PID).

If `backend_id` was already set by `AF_QUEUED`, `AF_READY` does not need to repeat it.

Everything before the markers is captured as startup logs. If `AF_READY` never appears (process exits or timeout expires), the start fails with captured stdout/stderr as the error.

**The wrapper script is responsible for emitting both markers**, not the sandbox server. The server cannot reliably know its externally routable hostname — in Apptainer the hostname may be the login node, in Docker it's a container ID, and on Slurm only the wrapper knows the allocated compute node.

The sandbox server provides a helper: on successful bind it prints `AF_BOUND {"port":9123}` to stdout (the port it actually bound to). This is *not* a marker the connector acts on — it's a signal the wrapper can use to construct the final `AF_READY` line with the correct routable hostname.

### Test Connection

Button visible when a remote sandbox is selected and connector is running. Runs a full cycle:

1. Write test secret file to `secret_dir`, verify it's readable from start command
2. Start command with dummy `run_key=test-<random>`
2. Wait for `AF_READY` marker on stdout
3. Tunnel to sandbox + hit `/health` (check version compatibility — see "Version compatibility")
4. Stop sandbox (kill start process for srun, or derived stop using `backend_id`)
5. Stream stdout/stderr at each step to the dashboard so user can debug

Requires SSH key-based auth (no interactive password prompts). If the user's HPC requires interactive auth, they must set up key-based access first.

## The Connector

A small async HTTP server that runs on the **host** (not in Docker). It bridges the agent (in Docker) to remote machines via SSH. Fully async — each run's proxy traffic is independent I/O, no threading needed.

**Why it runs on the host, not in Docker:** SSH is deeply tied to the host environment — `~/.ssh/config`, `ssh-agent`, ProxyJump, hardware keys. Mounting all of that into a container is fragile and breaks for non-trivial setups.

### What it does

1. Receives HTTP requests from the agent (via `host.docker.internal`)
2. Opens SSH connections to remote machines on demand
3. Executes start command and derived stop over SSH
4. Manages per-run SSH tunnels (bound to `127.0.0.1`, not `0.0.0.0`)
5. **Reverse-proxies** sandbox HTTP/SSE traffic — the agent talks to `http://host.docker.internal:<connector_port>/sandboxes/{run_key}/...` and the connector forwards to the remote sandbox over the SSH tunnel

The agent never sees a dynamic sandbox port. It always talks to the connector's single port. The connector routes by `run_key` path prefix.

### Lifecycle

```
autofyn start →
  1. docker compose up (agent, dashboard, db, sandbox)
  2. spawn connector in background (bash while-loop wrapper + PID file)

autofyn stop →
  1. POST /shutdown to connector (stops all active remote sandboxes, bounded 60s wait)
  2. kill connector (from PID file)
  3. docker compose down
```

The shutdown endpoint tells the connector to `destroy()` every active `ForwardState` — `scancel`, `docker rm -f`, or kill start processes. This prevents orphaned jobs/containers. If the endpoint times out (connector is dead), `autofyn stop` continues — orphan cleanup handles it on next `autofyn start`.

The connector starts idle — no SSH connections. SSH connections are opened on demand when a remote run starts, and closed when the run ends.

The connector is wrapped in a restart loop:

```bash
while true; do
  autofyn-connector --secret "$TOKEN" --port "$PORT"
  sleep 1
done
```

If the connector process crashes, the loop restarts it in 1 second. The wrapper PID is what `autofyn stop` kills. The wrapper itself is a trivial loop — it won't crash.

### Does not survive reboot

Neither does Docker. After a reboot, the user runs `autofyn start` and everything comes back — connector included. Same as any dev tool.

### How a remote run works

**Start:**
```
Agent generates sandbox_secret = secrets.token_hex(32)
Agent → POST /sandboxes/start to connector (host.docker.internal:<connector_port>)
  Body: {run_key, ssh_target, start_cmd (per-run), sandbox_type, sandbox_secret, host_mounts}
  Header: X-Connector-Secret (connector auth)
  Response: streaming NDJSON (one JSON object per line)

  Connector opens SSH to user@hpc.example.edu →
  Writes sandbox_secret to <secret_dir>/<run_key> on remote (mode 0600) →
  Passes AF_SANDBOX_SECRET_FILE=<secret_dir>/<run_key> as env to start command →
  Runs start command, streams stdout+stderr →
  Emits NDJSON events to the agent as they occur:
    {"event":"log","line":"Loading module apptainer..."}     (startup output)
    {"event":"queued","backend_id":"12345"}                  (from AF_QUEUED marker)
    {"event":"ready","host":"compute-7","port":9123}         (from AF_READY marker)
    {"event":"failed","error":"start command exited with 1"} (on failure)

  On "ready" → connector opens SSH tunnel: 127.0.0.1:<ephemeral> → compute-7:9123 →
  Stores ForwardState (including sandbox_secret for proxy auth, and the start SSH process handle) →
  NDJSON response stream to agent ends after "ready" or "failed".
  The start SSH process itself stays alive in ForwardState — for srun, killing it kills the allocation.
  The connector continues draining stdout/stderr from the start process into a ring buffer
  (last 100 lines, `collections.deque(maxlen=100)`) after the NDJSON stream ends. This
  prevents pipe buffer fill and provides crash logs (see "Remote sandbox logs").

Agent consumes events and owns all persistence:
  "log"    → writes startup_log audit event
  "queued" → writes sandbox_queued audit event + fills sandbox_backend_id column
  "ready"  → fills sandbox_remote_host, sandbox_remote_port columns

Agent uses connector as reverse proxy:
  http://host.docker.internal:<connector_port>/sandboxes/{run_key}/health
  Connector forwards with X-Internal-Secret: <sandbox_secret> to sandbox.
  Same HTTP API as local Docker, just prefixed with /sandboxes/{run_key}.
```

**Stop:**
```
Agent → POST /sandboxes/stop to connector
  Body: {run_key}
  Connector looks up ForwardState for run_key →
  If start_process is alive (srun): kills start_process (kills allocation) →
  If backend_id exists: runs derived stop over SSH (scancel or docker rm -f) →
  Deletes secret file on remote (rm ~/.autofyn/secrets/<run_key>) →
  Tears down SSH tunnel →
  Removes ForwardState →
  Closes SSH connection (if no other runs use this remote)
```

### Connector internal state

The connector tracks active tunnels with a `ForwardState` per run:

```python
@dataclass
class ForwardState:
    run_key: str
    ssh_target: str
    sandbox_type: str      # "slurm" or "docker" — for derived stop
    remote_host: str       # from AF_READY marker
    remote_port: int
    local_port: int        # ephemeral, bound to 127.0.0.1
    tunnel_process: asyncio.subprocess.Process   # SSH tunnel
    start_process: asyncio.subprocess.Process | None  # kept alive for srun (killing = stop)
    sandbox_secret: str    # per-run secret for sandbox auth
    backend_id: str | None # from AF_QUEUED or AF_READY — for scancel/docker rm
    log_buffer: deque[str] # ring buffer, maxlen=100 — post-ready stdout/stderr
    secret_file_path: str  # <secret_dir>/<run_key> on remote — deleted on stop
```

`dict[str, ForwardState]` keyed by `run_key`. On connector restart, active runs re-request tunnel setup via the reconnect flow.

The connector periodically probes each tunnel (HTTP to `127.0.0.1:<local_port>/health`). If a tunnel dies silently (broken pipe, SSH timeout), the connector tears it down, re-establishes the SSH tunnel to the same `remote_host:remote_port`, and resumes proxying. If re-establishment fails, it reports the tunnel as dead — the agent sees connection errors and enters `connector_lost` flow.

### Security

- Binds `127.0.0.1` or the Docker gateway address (must be reachable from Docker bridge via `host.docker.internal`, but not the wider LAN).
- **Per-session secret** — `autofyn start` generates a random token, passes it to both Docker (agent env var) and the connector (CLI arg). Every request must include `X-Connector-Secret` header. No token → 401.
- **Scoped commands** — connector receives start commands from the agent and derives stop from sandbox type. The connector is not an arbitrary shell — it only runs start commands delivered over the authenticated channel, and stop is limited to `scancel`, `docker rm -f`, or killing the start process. No separate DB validation needed; the shared secret on a localhost-only channel is sufficient.
- **Process group isolation** — all SSH child processes are started in their own process group. On Linux, `PR_SET_PDEATHSIG` ensures children die with the parent. On macOS, best effort: the connector wrapper traps EXIT/TERM and kills the process group (`trap 'kill 0' EXIT`). If the connector is SIGKILLed, the trap doesn't fire — the heartbeat self-termination is the fallback (sandbox dies after 30 min with no contact).

### Linux note

`host.docker.internal` needs `extra_hosts: ["host.docker.internal:host-gateway"]` in docker-compose. `autofyn start` adds this automatically.

### Network errors

**Brief** (WiFi blip, SSH keepalive timeout): The connector's tunnel health probe detects the dead tunnel, tears it down, and re-establishes a new SSH tunnel to the same `remote_host:remote_port`. The sandbox is still running — only the tunnel dropped. This is transparent to the agent. One or two HTTP requests may fail; the agent retries and succeeds on the new tunnel.

**Permanent** (remote host unreachable, sandbox OOM-killed, compute node died): The connector cannot re-establish the tunnel. Agent's HTTP calls fail repeatedly. The run transitions to `error` with a clear message: "Lost connection to remote sandbox." No silent retry. No fallback. The user sees the error immediately in the dashboard.

### Connector disconnect behavior

If the connector dies mid-run (crash, user kills it):

1. The SSH tunnel dies → agent's HTTP calls to connector reverse proxy fail with connection errors.
2. The run transitions to `connector_lost` status. Dashboard shows "Connector lost."
3. The restart loop revives the connector within ~1 second.

**Two distinct failure modes — not a fallback chain:**

- **Network error (tunnel drops, SSH timeout, WiFi blip):** Connector is alive, just the tunnel died. Connector re-establishes the SSH tunnel to the same `remote_host:remote_port`. The `start_process` is still alive on the connector — `srun` allocation is fine. **Identical behavior for all three backends.** Dashboard shows "Reconnecting..." with visible status. Run resumes transparently.

- **Connector process crash:** All SSH children die (process group kill). For `srun`, the allocation is gone — run transitions to `error` immediately. For `sbatch`/Docker remote, sandbox survives — the restarted connector re-establishes tunnel using `remote_host:remote_port` from `SandboxHandle`. Run resumes.

4. The agent waits up to `CONNECTOR_RECONNECT_TIMEOUT_SEC` (default: 5 minutes) with visible countdown in dashboard. If the timeout expires, the run transitions to `error`.

**Remote sandbox startup — same flow as local:**

```
starting → sandbox_created → bootstrap → running
```

Identical to local Docker. The `starting` phase just takes longer for remote (Slurm queue wait, SSH tunnel setup, container boot). The `startup_log` audit events stream into the feed during `starting` so the user sees progress instead of a silent spinner.

**One new run status:** `connector_lost`. Add to `RUN_STATUSES` and `ACTIVE_RUN_STATUSES`.

**Three new audit event types:**
- `sandbox_queued` — logged when `AF_QUEUED` is received, includes `backend_id`. Dashboard renders e.g. "Slurm job 12345 queued". Not a run status — just an informational event in the feed.
- `startup_log` — streaming lines from the start command during `starting` phase.
- `sandbox_start_failed` — start command exited without `AF_READY`, or `/health` timed out. Includes captured startup output.

A run in `starting` is already cancellable. For remote, cancellation kills the SSH subprocess and runs derived stop using `backend_id` if `AF_QUEUED` was received.

On failure (start command exits without `AF_READY`, or `/health` times out), a `sandbox_start_failed` audit event fires (with captured startup output) and the run transitions to `error`.

**Startup log streaming:** The connector streams both stdout and stderr from the start command as NDJSON `log` events to the agent (while simultaneously scanning stdout for `AF_QUEUED`/`AF_READY`). The agent writes each line as a `startup_log` audit event. The dashboard renders these in the run feed so the user sees Slurm queue progress, module load output, etc. This is not a new SSE channel — it uses the existing audit event stream. The connector never writes to the DB — it is purely a transport process.

**Timeouts (all in `db/constants.py`):**

| Constant | Default | Purpose |
|---|---|---|
| `SSH_CONNECT_TIMEOUT_SEC` | 30 | SSH connection to remote host |
| `SANDBOX_QUEUE_TIMEOUT_SEC` | 1800 | Waiting for `AF_READY` (covers Slurm queue) |
| `SANDBOX_BOOT_TIMEOUT_SEC` | 120 | `/health` after tunnel established |
| `SANDBOX_STOP_TIMEOUT_SEC` | 60 | Stop command execution |
| `CONNECTOR_RECONNECT_TIMEOUT_SEC` | 300 | Wait for connector to come back mid-run |

`queue_timeout` and `heartbeat_timeout` are per-sandbox (stored in config, editable in settings). All other timeouts are global constants.

**Implementation plumbing:**
- `db/constants.py`: add `RUN_STATUS_CONNECTOR_LOST = "connector_lost"` to `RUN_STATUSES` and `ACTIVE_RUN_STATUSES`. Add `sandbox_queued`, `startup_log`, and `sandbox_start_failed` to `AUDIT_EVENT_TYPES`.
- Dashboard frontend: `RunStatusBadge` renders `connector_lost` with a warning color + "Connector lost" message. Control endpoints (pause/stop) still work — user can stop a disconnected run.
- `autofyn/lifecycle/round_loop.py`: catch `ConnectorLostError` from sandbox client, transition to `connector_lost`, wait on connector reconnect event with timeout, resume or fail.

### Abandoned sandbox self-termination

If the user's laptop dies and never comes back, the remote sandbox sits on the HPC consuming resources indefinitely. The sandbox server must protect against this:

- The sandbox tracks the timestamp of the last HTTP request from the agent.
- If no request arrives for `SANDBOX_HEARTBEAT_TIMEOUT_SEC` (default: 30 minutes, configurable per remote sandbox), the sandbox self-terminates with exit code 0.
- The connector sends an explicit `GET /heartbeat` to each active remote sandbox every 60 seconds. This is independent of the agent's round cadence — a long Claude session, a long tool call, an open SSE stream, or a paused run all have no agent HTTP requests, but the connector heartbeat keeps the sandbox alive.
- The agent does not need to do anything extra. The connector owns the heartbeat because it owns the tunnel.

**Two cleanup paths depending on whether autofyn is still running:**

1. **Autofyn is up, laptop is fine, sandbox self-terminates** (e.g. agent paused too long, network partition resolved after timeout): The agent's next HTTP call through the connector fails → run transitions to `error` → `destroy()` runs derived stop (idempotent) → DB cleared. Normal crash flow, nothing special needed.

2. **Laptop crashed, autofyn is dead:** The heartbeat prevents the remote sandbox from running forever on the HPC. When the user eventually runs `autofyn start`, orphan cleanup finds `sandbox_type IS NOT NULL`, runs derived stop (idempotent — sandbox already exited), marks run `crashed`, clears DB.

The heartbeat solves the "abandoned remote process eating HPC resources" problem. The agent-side cleanup is the same crash flow that already handles sandbox OOM/preemption.

Add `SANDBOX_HEARTBEAT_TIMEOUT_SEC = 1800` to `db/constants.py`. Pass as `AF_HEARTBEAT_TIMEOUT` env var to start command.

## Data passed to start command

**Environment variables** set by the connector before running the start command over SSH (no high-value user credentials — only operational config and the per-run sandbox auth token):

| Env var | Type | Description |
|---|---|---|
| `AF_RUN_KEY` | string | Unique run identifier |
| `AF_HOST_MOUNTS_JSON` | JSON | `[{host_path, container_path, mode}]` |
| `AF_APPTAINER_BINDS` | string | Pre-computed `-B` flags (Slurm only): `-B /data:/data:ro -B /scratch:/scratch:rw` |
| `AF_DOCKER_VOLUMES` | string | Pre-computed `-v` flags (Docker only): `-v /data:/data:ro -v /scratch:/scratch:rw` |
| `AF_SANDBOX_SECRET_FILE` | string | Path to `0600` file containing per-run sandbox secret (connector writes this before start) |
| `AF_HEARTBEAT_TIMEOUT` | string | Seconds — sandbox self-terminates if no agent contact |

Note: `AF_SANDBOX_PORT` is NOT set by the connector — the start command passes `AF_SANDBOX_PORT=0` to the sandbox server (OS picks a free port).

**High-value user credentials are NOT passed through start command env.** Claude tokens, git tokens, and other secrets that grant access to external services are injected over the authenticated tunnel after `/health` passes:

```
Agent → POST /sandboxes/{run_key}/env to connector (reverse proxy) →
  Connector forwards to sandbox → POST /env with {claude_token, git_token, ...}
  Sandbox stores in memory, never on disk.
```

This avoids leaking secrets into Slurm job metadata, `/proc/<pid>/environ`, scheduler logs, or `ps` output on shared clusters. The sandbox secret is never passed as an env var for remote runs — the connector writes it to a `0600` temp file on the remote and passes `AF_SANDBOX_SECRET_FILE=<path>` instead. The sandbox server reads the secret from this file. This prevents exposure in process environment, `ps` output, and Slurm job metadata on shared clusters.

The sandbox server adds a `POST /env` endpoint (auth required) that accepts a JSON dict of env vars and merges them into `os.environ` in-memory. The agent calls this once after health check, before bootstrap.

## Backend architecture

### Class hierarchy

One base class, one interface for the agent. Easily extendable for new backend types.

```python
@dataclass(frozen=True)
class SandboxHandle:
    run_key: str
    url: str               # agent talks to this URL — always
    backend_id: str | None # container id, job id, etc.
    sandbox_secret: str    # per-run secret for sandbox HTTP auth
    sandbox_id: str | None # UUID of remote sandbox config (None for local)
    sandbox_type: str | None   # "slurm" | "docker" | None (local)
    remote_host: str | None    # from AF_READY (needed for connector reconnect)
    remote_port: int | None    # from AF_READY (needed for connector reconnect)


class SandboxBackend(ABC):
    """Base class. Agent calls these methods — doesn't know local vs remote."""

    @abstractmethod
    async def create(self, run_key, start_cmd, host_mounts, health_timeout) -> SandboxHandle: ...

    @abstractmethod
    async def destroy(self, handle: SandboxHandle) -> None: ...

    @abstractmethod
    async def destroy_all(self) -> None: ...

    @abstractmethod
    async def get_logs(self, run_key, tail) -> list[str]: ...


class DockerLocalBackend(SandboxBackend):
    """Local Docker via Docker API. Existing behavior."""
    # create: docker run → return handle with url=http://localhost:<port>
    # destroy: docker rm -f <backend_id>
    # get_logs: docker logs <backend_id>


class SlurmBackend(SandboxBackend):
    """Remote Slurm via connector. SSH + srun/sbatch."""
    # create: POST /sandboxes/start → connector → SSH → srun → tunnel → handle
    # destroy: kill start_process (srun) or scancel (sbatch)
    # get_logs: GET /sandboxes/{run_key}/logs on connector (ring buffer)


class DockerRemoteBackend(SandboxBackend):
    """Remote Docker via connector. SSH + docker run."""
    # create: POST /sandboxes/start → connector → SSH → docker run → tunnel → handle
    # destroy: docker rm -f <backend_id> over SSH
    # get_logs: docker logs --tail N <backend_id> over SSH (container survives crashes)
```

The agent code is one path: `backend.create()`, talk to `handle.url`, `backend.destroy(handle)`. Adding a new backend (e.g. Kubernetes) means one new subclass — no changes to the agent.

`SlurmBackend` and `DockerRemoteBackend` share the connector transport — both use `POST /sandboxes/start`, NDJSON streaming, SSH tunnels. The difference is the derived stop command and log source. A shared `RemoteBackendMixin` or base class can hold the common connector logic.

For local Docker runs, `sandbox_secret` is the existing `SANDBOX_INTERNAL_SECRET`. For remote runs, the agent generates a fresh `secrets.token_hex(32)` per run.

**Handle persistence — two levels:**
- **Live agent (connector blip, tunnel re-establishment):** `SandboxHandle` in memory (`_handles: dict[str, SandboxHandle]`). Agent uses `remote_host`/`remote_port` from the handle to re-request tunnel setup.
- **Agent restart (crash, reboot):** In-memory handles are gone. The runs table has `sandbox_remote_host`/`sandbox_remote_port` snapshot columns. Orphan cleanup reads these to re-establish tunnels or run derived stop.

### `SandboxPool` — per-run backend factory

Pool is instantiated once. Backend choice is per-run (from sandbox selection in dashboard, passed in `StartRequest`).

```python
class SandboxPool:
    def __init__(self):
        self._docker_local = DockerLocalBackend()
        self._handles: dict[str, SandboxHandle] = {}

    async def _resolve_backend(self, sandbox_id: str | None) -> SandboxBackend:
        if sandbox_id is None:
            return self._docker_local
        config = await db.get_setting(f"remote_sandbox:{sandbox_id}")
        parsed = json.loads(config.value)
        if parsed["type"] == "slurm":
            return SlurmBackend(
                connector_url=self._connector_url,
                sandbox_id=sandbox_id,
                ssh_target=parsed["ssh_target"],
                queue_timeout=parsed["queue_timeout"],
                heartbeat_timeout=parsed["heartbeat_timeout"],
            )
        return DockerRemoteBackend(
            connector_url=self._connector_url,
            sandbox_id=sandbox_id,
            ssh_target=parsed["ssh_target"],
            heartbeat_timeout=parsed["heartbeat_timeout"],
        )
```

`StartRequest` gains `sandbox_id: str | None` and `start_cmd: str | None`. The dashboard sends the selected sandbox UUID and the (possibly edited) start command. For local Docker, both are `None`. The agent resolves the remote config from DB and snapshots resolved values onto the run row for cleanup.

### Per-repo + per-sandbox config in DB

Remote sandbox configs: `remote_sandbox:{uuid}`. Fields (JSON value):
- `name`: string (user-chosen display label)
- `ssh_target`: string (e.g. `user@hpc.example.edu`)
- `type`: `"slurm"` | `"docker"` (determines derived stop/logs commands)
- `default_start_cmd`: string (pre-filled in run modal, user can override per-run)
- `secret_dir`: string (path on remote for secret files, default `~/.autofyn/secrets` — must be on shared filesystem visible to compute nodes)
- `queue_timeout`: int (seconds — how long to wait for `AF_READY`, initialized to `SANDBOX_QUEUE_TIMEOUT_SEC` on creation)
- `heartbeat_timeout`: int (seconds — sandbox self-terminates after no contact, initialized to `SANDBOX_HEARTBEAT_TIMEOUT_SEC` on creation)

Per-run start command: stored on the runs table as `sandbox_start_cmd` (the actual command used, after any per-run edits).

Last-used start command: `last_start_cmd:{repo}:{sandbox_id}` — persisted after each run so the next run pre-fills with the last-used command for this repo+target.

Mounts: `local_mounts:{repo}` and `remote_mounts:{repo}:{sandbox_id}` (separate keys, same schema). Keyed by `sandbox_id` (UUID), not display name.

## Orphan cleanup

New nullable columns on `runs` table — a **cleanup snapshot** of resolved values at run creation time:

```python
sandbox_id: Mapped[str | None]          # UUID of the remote sandbox config
sandbox_type: Mapped[str | None]        # "slurm" or "docker" — determines stop/logs behavior
sandbox_backend_id: Mapped[str | None]  # from AF_QUEUED/AF_READY marker (job id, container id)
sandbox_ssh_target: Mapped[str | None]  # resolved SSH target at run start
sandbox_start_cmd: Mapped[str | None]   # for debugging only — not used by cleanup
sandbox_remote_host: Mapped[str | None] # from AF_READY marker
sandbox_remote_port: Mapped[int | None] # from AF_READY marker
```

No `stop_cmd` or `logs_cmd` columns — stop is derived from `sandbox_type` + context:
- Slurm with `backend_id` (`sbatch`) → `scancel <backend_id>`
- Slurm without `backend_id` (`srun`) → SSH session death already killed the allocation, no action needed
- Docker → `docker rm -f <backend_id>`

Cleanup and log retrieval use these snapshot columns directly — they never look up the live `remote_sandbox:{uuid}` settings row. This means renaming, editing, or deleting a remote sandbox config cannot break cleanup for active or orphaned runs.

**Lifecycle:**
- Before start command → write `sandbox_id`, `sandbox_type`, `sandbox_ssh_target`, `sandbox_start_cmd` immediately (resolved from config + per-run override)
- On `AF_QUEUED` → fill `sandbox_backend_id` immediately (enables cleanup of queued jobs)
- On `AF_READY` → fill `sandbox_remote_host`, `sandbox_remote_port` (and `sandbox_backend_id` if not already set by `AF_QUEUED`)
- After stop succeeds → clear all columns
- Never clear on failure — preserves cleanup handle for retry

**Cleanup runs in two places:**

1. **Agent startup** (before `mark_crashed_runs()`): query `sandbox_type IS NOT NULL`. If `sandbox_backend_id` exists, derive stop command (`scancel` or `docker rm -f`) and run over SSH to `sandbox_ssh_target`. If no `backend_id` (srun), the SSH session death already killed the allocation — just mark the run as crashed. No settings lookup needed.
2. **Connector restart**: run deferred cleanup for any pending orphans.

### Cancellation during startup

Start command may block for a long time (Slurm queue). If cancelled before `AF_READY` marker:
- Connector kills SSH subprocess (SIGTERM → SIGKILL)
- If `AF_QUEUED` was received, `backend_id` is already on the runs table → derived stop runs (e.g. `scancel 12345` for Slurm, `docker rm -f <id>` for Docker)
- If `AF_QUEUED` was never received, killing the SSH subprocess is sufficient — for Slurm with `srun`, the job is tied to the SSH session
- Startup output captured, persisted as `sandbox_start_failed` audit event

### Orphaned queued jobs

The heartbeat self-termination only works after the sandbox server is running. For queued jobs that haven't started yet, cleanup depends on having a `backend_id`.

**Two layers of protection:**

1. **`srun` (recommended).** The job is tied to the SSH connection. SSH dies → `srun` dies → Slurm cancels the allocation. No `backend_id` needed. Simplest and safest.

2. **`AF_QUEUED` marker (required for `sbatch`).** Start commands that use `sbatch` must emit `AF_QUEUED {"backend_id":"12345"}` immediately after submission. The agent persists `backend_id` to the runs table right away. Orphan cleanup can then `scancel` the job even if the laptop died seconds later.

If using `sbatch` without `AF_QUEUED`, orphan cleanup cannot cancel queued jobs. Document this clearly.

## Sandbox logs

**One source, one code path — local and remote identical.**

Every sandbox backend keeps a **ring buffer** (`collections.deque(maxlen=100)`) of the last 100 lines of sandbox stdout/stderr. The agent calls `backend.get_logs(run_key, tail)` — same method, same result, regardless of backend type.

| Backend | `get_logs()` implementation |
|---|---|
| Local Docker | Ring buffer — drains container stdout into `deque(maxlen=100)` (container may be deleted after run) |
| Slurm `srun` | Ring buffer — connector drains start SSH process stdout into `deque(maxlen=100)` |
| Docker remote | `docker logs --tail N <backend_id>` over SSH (container survives crashes, no ring buffer needed) |

One API, backend-specific internals. Always available — sandbox alive or dead.

**On crash:**
1. Agent's next HTTP call to sandbox fails → crash detected
2. Agent calls `backend.get_logs(run_key, 100)` → ring buffer contents
3. Agent writes a `sandbox_crash` audit event with the log lines as payload
4. Dashboard renders: "Sandbox crashed" with **[See more]** → expands to show the full 100 lines

**If the ring buffer is unavailable** (connector crashed, local pool restarted): show "Logs unavailable." Don't pretend `startup_log` events are runtime logs — they only cover boot.

**`sbatch` limitation:** `sbatch` stdout goes to Slurm's output file, not through the SSH pipe. Crash logs are not available. The dashboard warns when a Slurm start command contains `sbatch`: *"Crash logs unavailable with sbatch. Use srun for full observability."*

## Sandbox image

CI publishes both Docker and SIF artifacts from the same pipeline:

```
ghcr.io/signalpilot-labs/autofyn-sandbox:stable          # Docker (production branch)
ghcr.io/signalpilot-labs/autofyn-sandbox:nightly          # Docker (main branch)
ghcr.io/signalpilot-labs/autofyn-sandbox-sif:stable       # SIF as OCI artifact (production)
ghcr.io/signalpilot-labs/autofyn-sandbox-sif:nightly      # SIF as OCI artifact (main)
```

The SIF is built from the Docker image in the same GitHub Actions workflow (see "CI changes"). Same code, same protocol version, just a different artifact format.

**User setup (one-time per version):**

```bash
# Slurm/Apptainer cluster:
module load apptainer
apptainer pull ~/.autofyn/sandbox.sif oras://ghcr.io/signalpilot-labs/autofyn-sandbox-sif:stable

# Docker remote:
docker pull ghcr.io/signalpilot-labs/autofyn-sandbox:stable
```

**Update** is the same command — overwrite the `.sif` or pull the latest Docker image. No CLI tools to install on the remote. No `autofyn-remote`. Just one download command.

Server changes in `sandbox/server.py`:
- Reads `AF_SANDBOX_PORT` from env (required for remote, falls back to constant default for local Docker).
- Reads sandbox secret from `AF_SANDBOX_SECRET` (env var, local Docker) or `AF_SANDBOX_SECRET_FILE` (file path, remote). Exactly one must be set — both or neither is an error.
- On successful bind, prints `AF_BOUND {"port":N}` to stdout — a helper signal for start commands. This is *not* a marker the connector acts on; the start command emits `AF_READY` with the routable hostname.

### Apptainer writable runtime layout

Apptainer `.sif` images are read-only by default. The sandbox needs writable directories for repo checkout, Claude sessions, temp files, and logs. The reference start command must bind a per-run writable root:

```
<user-chosen scratch dir>/$AF_RUN_KEY/
  repo/           → /home/agentuser/repo
  home/           → /home/agentuser
  tmp/            → /tmp
  claude/         → /home/agentuser/.claude
  logs/           → /var/log/autofyn
```

The start command creates this layout and binds it. The scratch directory is the user's choice — `~/scratch`, `/tmp`, `$SCRATCH`, whatever their cluster provides. AutoFyn does not need to know the path. User-configured host mounts (via `$AF_APPTAINER_BINDS`) are *additional* — they do not replace the required writable runtime dirs.

### Version compatibility

The local agent and remote `.sif` must agree on protocol. `autofyn update` updates local images but cannot update the user's remote `.sif` automatically.

- `/health` response gains a `protocol_version` field (integer, bumped on breaking API changes) and `image_tag` (informational).
- The agent checks `protocol_version` after health check. If incompatible, the run fails immediately with a clear error: "Remote sandbox protocol version N, agent expects M. Rebuild your .sif: `apptainer build sandbox.sif docker://ghcr.io/.../autofyn-sandbox:<tag>`".
- Test Connection also checks version compatibility and shows the mismatch.

### Remote network requirements

The remote sandbox needs outbound HTTPS for:
- Anthropic API (Claude)
- GitHub API (clone, PR creation)
- Package registries (pip, npm — if the task installs deps)

Many HPC compute nodes have restricted outbound internet. This is a hard requirement — if the sandbox can't reach Anthropic, the Claude session fails immediately. The sandbox respects `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` for proxied clusters.

## CI changes

Add a SIF build job to `.github/workflows/docker-publish.yml` that runs after the Docker manifest merge:

```yaml
build-sif:
  needs: manifest
  runs-on: ubuntu-latest
  permissions:
    contents: read
    packages: write

  steps:
    - name: Install Apptainer
      uses: eWaterCycle/setup-apptainer@v2

    - name: Log in to GHCR
      uses: docker/login-action@v4
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Build SIF from Docker image
      run: |
        SHA="${GITHUB_SHA::7}"
        BRANCH="${GITHUB_REF_NAME}"
        IMAGE="ghcr.io/signalpilot-labs/autofyn-sandbox"
        SIF_IMAGE="ghcr.io/signalpilot-labs/autofyn-sandbox-sif"

        apptainer build sandbox.sif "docker://${IMAGE}:${SHA}"

        # Push as OCI artifact
        apptainer push sandbox.sif "oras://${SIF_IMAGE}:${SHA}"
        if [ "$BRANCH" = "production" ]; then
          apptainer push sandbox.sif "oras://${SIF_IMAGE}:stable"
        elif [ "$BRANCH" = "main" ]; then
          apptainer push sandbox.sif "oras://${SIF_IMAGE}:nightly"
        fi
```

Same tag convention as Docker images: short SHA + `stable` (production) or `nightly` (main). The SIF is built from the multi-arch Docker manifest, so it matches exactly.

## Docker compose changes

- Remove hard `depends_on: sandbox` from agent. Agent checks Docker sandbox availability only when backend=docker.
- Add `extra_hosts: ["host.docker.internal:host-gateway"]` to agent (Linux).
- Pass `CONNECTOR_SECRET` and `CONNECTOR_PORT` as env vars to agent container (for connector reverse proxy URL).

## Implementation plan

### Phase 0: SSE consolidation (done)

Landed in PR #238.

### Phase 1: Backend abstraction

1. Extract `SandboxBackend` Protocol + `SandboxHandle` (with `sandbox_secret`, `sandbox_id`, `sandbox_type`, remote fields)
2. Move Docker code into `DockerLocalBackend`. Pool becomes factory with `_resolve_backend(sandbox_id)`. Add ring buffer (drain container stdout, `deque(maxlen=100)`) — same `get_logs()` interface as remote backends.
3. Add `SlurmBackend` and `DockerRemoteBackend` — both send commands via connector reverse proxy. Slurm stop: kill `start_process` (srun) or `scancel` (sbatch). Docker stop: `docker rm -f`.
4. `sandbox/server.py`: read `AF_SANDBOX_PORT` from env; read secret from `AF_SANDBOX_SECRET` (env, local) or `AF_SANDBOX_SECRET_FILE` (file, remote) — exactly one must be set; add `POST /env` endpoint for secret injection; add `protocol_version` to `/health` response; emit `AF_BOUND` helper on bind
5. DB migration: add cleanup snapshot columns (`sandbox_id`, `sandbox_type`, `sandbox_backend_id`, `sandbox_ssh_target`, `sandbox_start_cmd`, `sandbox_remote_host`, `sandbox_remote_port`)
6. Orphan cleanup before `mark_crashed_runs()` — Slurm with `backend_id`: `scancel`. Slurm without (srun): SSH death killed it, just mark crashed. Docker: `docker rm -f`. No settings lookup.
7. Add `connector_lost` run status. Add `sandbox_queued`, `startup_log`, and `sandbox_start_failed` audit event types. Everything else (`starting`, `sandbox_created`) already exists.
8. Add timeout constants to `db/constants.py`

### Phase 2: Connector

9. `autofyn-connector` — async HTTP server on host; reverse-proxies `/sandboxes/{run_key}/*` to remote sandbox over SSH tunnel; manages `ForwardState` per run; periodic tunnel health probes; heartbeat to active sandboxes
10. `autofyn start` spawns connector with restart loop + PID file; passes `CONNECTOR_SECRET` + `CONNECTOR_PORT` to both connector and agent
11. `autofyn stop`: POST `/shutdown` to connector (bounded 60s — stops all active remote sandboxes, deletes secret files), then kill connector
12. Connector health check endpoint: `/health` returns active tunnels, connector version (for dashboard status + test connection)
12a. `GET /sandboxes/{run_key}/logs?tail=N` — returns ring buffer (max 100 lines). Works whether sandbox is alive or dead.
13. Startup log streaming: connector streams start command stdout+stderr as NDJSON events to agent (scanning stdout for `AF_QUEUED`/`AF_READY`)

### Phase 3: Dashboard UI

14. Settings page: "Remote Sandboxes" CRUD section (name, SSH target, type, default start command) — each config gets a UUID
15. Run creation: sandbox radio group (Local + named remotes); editable start command pre-filled from last-used or settings default; switching sandbox swaps host mounts label and saved set; `StartRequest` gains `sandbox_id: str | None` and `start_cmd: str | None`
16. API endpoints — `GET/POST/PUT/DELETE /api/sandboxes`, `POST /api/sandboxes/{id}/test` (test includes version compat check)
17. `RunStatusBadge` renders `connector_lost` (warning badge)
18. Dashboard prevents deletion of remote sandbox configs that have active runs

### Phase 4: CI + tests + docs

19. Add SIF build job to `docker-publish.yml` — builds from Docker image, publishes as OCI artifact with same tag convention (`stable`/`nightly`/SHA)
20. `test_remote_backend.py` — Slurm and Docker remote backends with fake connector
21. `test_connector.py` — connector HTTP server unit tests (reverse proxy, tunnel management, NDJSON streaming)
22. `docs/remote-sandbox.md` — setup guide: SSH key setup, SIF download, example start commands for Slurm and Docker, writable layout, network requirements, proxy config

## Constraints

1. **Two remote types: Slurm and Docker.** Both use SSH. Stop and logs are derived from type.
2. **SSH auth must be non-interactive.** Key-based auth only. No password prompts, no 2FA during connection.
3. **One connector process.** Multiple simultaneous remote runs on different hosts are fine — each gets its own SSH connection + tunnel.
4. **Preemption recovery is out of scope.** If the remote sandbox dies (OOM, preemption, node failure), the run fails.
5. **Remote sandbox needs outbound HTTPS.** Must reach Anthropic API, GitHub, and package registries.
6. **Version parity.** Agent and remote `.sif` must have matching `protocol_version`. Mismatches fail fast with a rebuild instruction.
7. **No remote CLI tool.** Users download the SIF or pull the Docker image. One command.
8. **Remote mount paths must be absolute POSIX**, not in `/proc`/`/sys`/`/dev`, and contain only `[a-zA-Z0-9._/-]` (no spaces, shell metacharacters). `AF_APPTAINER_BINDS`/`AF_DOCKER_VOLUMES` are built from these paths — allowing arbitrary characters would break shell expansion. Cannot check existence — paths are on the remote machine.

## Example start commands

Reference start commands for the run modal. The user edits these to match their cluster. Stop and logs are derived by AutoFyn from the sandbox type — the user never writes stop/logs commands.

**Key contract:** The start command must:
1. Start the sandbox server with `AF_SANDBOX_PORT=0` (OS picks a free port on the target machine)
2. Wait for `AF_BOUND {"port":N}` in sandbox output to learn the actual port
3. Emit `AF_READY {"host":"<routable-host>","port":<port>}` on stdout
4. Optionally emit `AF_QUEUED {"backend_id":"<id>"}` early (for Slurm `sbatch`)

Never pre-pick a port on the login node — it may conflict on the compute node. Always let the sandbox bind port 0 and read the actual port from `AF_BOUND`.

**Slurm + Apptainer (interactive with `srun`):**
```bash
# Simple — srun ties the job to the SSH session, so cleanup is automatic.
# User tweaks: --partition, --gres, -n, --mem, -t per run.
# Sandbox binds port 0 (OS picks a free port on the compute node).
# AF_BOUND tells us which port was actually assigned.
module load apptainer/1.4.2 && \
ROOT=~/scratch/autofyn/$AF_RUN_KEY && \
mkdir -p $ROOT/{repo,home,tmp,claude,logs} && \
srun --partition=gpu --gres=gpu:1 -n 4 --mem=16G -t 4:00:00 \
  bash -c "
    AF_SANDBOX_PORT=0 AF_SANDBOX_SECRET_FILE=\$AF_SANDBOX_SECRET_FILE \
    apptainer exec --nv \
      -B $ROOT/repo:/home/agentuser/repo \
      -B $ROOT/home:/home/agentuser \
      -B $ROOT/tmp:/tmp \
      -B $ROOT/claude:/home/agentuser/.claude \
      -B $ROOT/logs:/var/log/autofyn \
      \$AF_APPTAINER_BINDS \
      ~/.autofyn/sandbox.sif python3 -m sandbox.server 2>&1 | tee $ROOT/server.log &
    SERVER_PID=\$!
    while ! grep -q 'AF_BOUND' $ROOT/server.log 2>/dev/null; do sleep 0.2; done
    PORT=\$(grep -o 'AF_BOUND {\"port\":[0-9]*}' $ROOT/server.log | grep -o '[0-9]*')
    echo \"AF_READY {\\\"host\\\":\\\"\$(hostname)\\\",\\\"port\\\":\$PORT}\"
    wait \$SERVER_PID
  "
```

**Slurm + Apptainer (batch with `sbatch`) — advanced:**

`sbatch` detaches from the SSH session, so cleanup requires `AF_QUEUED` with the job ID. The connector already writes the secret file — the `sbatch` wrapper just passes `AF_SANDBOX_SECRET_FILE` through. Start command must: `sbatch` → emit `AF_QUEUED {"backend_id":"<job_id>"}` → poll for `AF_BOUND` in sandbox output → emit `AF_READY`. See setup guide for a complete example.

**Docker on remote:**
```bash
# Simplest case. User tweaks: --gpus, --cpus, --memory.
# Loopback only — sandbox is only reachable through the SSH tunnel.
# Start process exits after AF_READY. Logs retrieved via docker logs over SSH.
docker run -d -p 127.0.0.1::8080 \
  -e AF_SANDBOX_PORT=8080 \
  -e AF_SANDBOX_SECRET_FILE=/run/secrets/sandbox_secret \
  -v $AF_SANDBOX_SECRET_FILE:/run/secrets/sandbox_secret:ro \
  --gpus 1 \
  $AF_DOCKER_VOLUMES \
  --name autofyn-$AF_RUN_KEY \
  ghcr.io/signalpilot-labs/autofyn-sandbox:stable && \
while ! docker logs autofyn-$AF_RUN_KEY 2>&1 | grep -q "AF_BOUND"; do sleep 0.2; done && \
PORT=$(docker port autofyn-$AF_RUN_KEY 8080 | cut -d: -f2) && \
echo "AF_READY {\"host\":\"127.0.0.1\",\"port\":$PORT,\"backend_id\":\"autofyn-$AF_RUN_KEY\"}"
```

**Stop is derived automatically:**
- Slurm with `srun` → connector kills the start SSH process (kills the allocation). After connector/laptop death, no action needed — SSH death already killed `srun`.
- Slurm with `sbatch` → `scancel <backend_id>` (works for queued, running, or finished jobs)
- Docker → `docker rm -f <backend_id>` (works for running or stopped containers)
