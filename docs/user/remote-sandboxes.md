# Remote Sandboxes

By default, AutoFyn runs each sandbox in a local Docker container. Remote sandboxes let you run on HPC clusters, GPU servers, or any machine you can SSH into.

## How it works

1. AutoFyn SSH-tunnels to the remote machine via the **connector** (a local process started automatically by `autofyn start`)
2. Your **start command** runs on the remote — it launches the sandbox container/process
3. The sandbox binds a port and prints `AF_BOUND port=8080`
4. Once healthy, it prints `AF_READY host=<compute-node> port=8080`
5. The connector establishes a reverse tunnel and proxies all traffic

The agent talks to the remote sandbox exactly like a local one — same HTTP API, same security.

## Setup

### 1. Pull the sandbox image on the remote

**Docker remote:**

```bash
docker pull ghcr.io/signalpilot-labs/autofyn-sandbox:stable
```

**Slurm / Apptainer (HPC):**

```bash
# On the remote (or via SSH)
ssh user@remote "source /etc/profile && module load apptainer && mkdir -p ~/.autofyn && apptainer pull ~/.autofyn/sandbox.sif docker://ghcr.io/signalpilot-labs/autofyn-sandbox:stable"
```

### 2. Ensure SSH access

You need passwordless SSH to the remote (key-based auth). Test it:

```bash
ssh user@remote-host "echo ok"
```

You can use an SSH config alias (e.g. `Host mycluster` in `~/.ssh/config`).

### 3. Add the sandbox in the dashboard

Go to **Settings → Remote Sandboxes → Add Sandbox**.

| Field | Description |
|-------|-------------|
| **Name** | Display name (e.g. "GPU Server", "HPC Cluster") |
| **Type** | `Docker` or `Slurm` |
| **SSH Target** | `user@host` or SSH config alias |
| **Start Command** | Shell command that launches the sandbox (see below) |
| **Startup Timeout** | Max seconds to wait for `AF_READY` (default: 1800 for Slurm queues) |
| **Inactivity Timeout** | Sandbox self-terminates after this many seconds idle (default: 1800) |

### 4. Start a run using the remote sandbox

In the **New Run** modal, expand the **Sandbox** section and select your remote sandbox instead of "Docker (local)". AutoFyn remembers your last choice per repo.

## Start command examples

### Docker remote

```bash
docker run --rm -p 8080:8080 ghcr.io/signalpilot-labs/autofyn-sandbox:stable
```

### Slurm / Apptainer

```bash
source /etc/profile && module load apptainer/1.4.2 && srun -p my_partition -n 1 -c 4 --mem=4G apptainer exec --pwd /opt/autofyn --writable-tmpfs -B $HOME ~/.autofyn/sandbox.sif python3 -m server
```

With GPU access:

```bash
source /etc/profile && module load apptainer/1.4.2 && srun -p gpu -n 1 -c 4 --mem=8G --gres=gpu:1 apptainer exec --nv --pwd /opt/autofyn --writable-tmpfs -B $HOME ~/.autofyn/sandbox.sif python3 -m server
```

Key flags:

- `source /etc/profile` — non-interactive SSH doesn't source profile, so modules won't load without this
- `-n 1` — only one task. `-n > 1` would spawn > 1 processes both trying to bind port 8080
- `-c 4` — request 4 CPU cores (adjust to your needs)
- `--mem=4G` — memory limit per node
- `--gres=gpu:1` — request 1 GPU (Slurm generic resource)
- `--nv` — Apptainer flag to expose NVIDIA GPUs inside the container
- `--writable-tmpfs` — the SIF image is read-only; this adds a tmpfs overlay for writes
- `-B $HOME` — binds your home directory for git config, SSH keys, etc.

## Timeline events

When a remote sandbox starts, you'll see these milestones in the dashboard feed:

1. **Run Starting** — run created
2. **Sandbox Queued** — job submitted (shows Slurm job ID)
3. **Sandbox Allocated** — resources allocated (Slurm only)
4. **Sandbox Started** — sandbox is healthy and ready

Startup log lines (srun output, server boot, etc.) are stored in the audit log but not shown in the feed.

## Troubleshooting

**Sandbox start failed / timeout:**
- Check `autofyn logs` for connector errors
- SSH into the remote and run the start command manually to see output
- For Slurm: check `squeue -u $USER` to see if the job is stuck in queue
- Increase the **Startup Timeout** in sandbox settings (Slurm queues can take minutes)

**"Start command exited without AF_READY":**
- The process exited before printing `AF_READY`. Run the command manually on the remote to see errors
- Common causes: wrong module name, missing SIF file, port already in use

**Connection drops during run:**
- The connector auto-reconnects. If it can't, the run status changes to `connector_lost`
- Check `~/.autofyn/.connector.log` for details
