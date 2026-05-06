# Configuration

AutoFyn has three layers of configuration: a YAML config file, dashboard settings (stored in the database), and per-repo settings.

## Config file hierarchy

```
defaults (hardcoded)
  ↓ overridden by
~/.autofyn/config.yml (global)
  ↓ overridden by
.autofyn/config.yml (per-project, in your repo root)
```

Per-project config takes precedence over global config, which takes precedence over defaults.

### Config file sections

```yaml
database:
  host: db
  port: 5432
  name: autofyn
  user: autofyn
  password: autofyn
  pool_size: 5
  max_overflow: 10

sandbox:
  url: http://sandbox:8923
  max_vms: 10
  vm_memory_mb: 512
  vm_vcpus: 1
  vm_timeout_sec: 300
  exec_timeout_sec: 120
  clone_timeout_sec: 300
  health_timeout_sec: 5
  log_level: info

agent:
  port: 8500
  max_budget_usd: 0  # 0 = unlimited

dashboard:
  api_port: 3401
  ui_port: 3400
```

Most users won't need to touch this file. The defaults work for local development. The main reason to edit it is to adjust sandbox resource limits (`vm_memory_mb`, `vm_vcpus`) or timeouts.

## Dashboard settings

These are stored in the PostgreSQL database, not in config files. Set them via the dashboard UI or CLI:

| Setting | CLI flag | Description |
|---------|----------|-------------|
| Claude token | `--claude-token` | Added to a token pool (supports multiple) |
| Git token | `--git-token` | GitHub personal access token for cloning/pushing |
| GitHub repo | `--github-repo` | `owner/repo` slug for the active repository |
| Budget | `--budget` | Default max spend per run in USD (0 = unlimited) |
| API key | `--api-key` | Protects dashboard API (optional) |

```bash
autofyn settings set --claude-token sk-ant-... --git-token ghp_...
autofyn settings set --github-repo owner/repo
autofyn settings set --budget 10.00
```

AutoFyn auto-detects tokens on first start from `claude setup-token` (browser OAuth) and `gh auth token`.

## Per-repo settings

These are configured in the dashboard UI (New Run modal or Settings page) and stored in the database, keyed by `owner/repo`.

### Environment variables

Set under **Environment Variables** in the New Run modal. Format: `KEY=value` per line.

```
API_KEY=sk-your-key
DATABASE_URL=postgres://localhost:5432/mydb
```

Env vars are encrypted at rest and injected into the sandbox via `POST /env` — they never appear in container env, SSH args, or logs.

### Host mounts

Bind-mount directories from your host into the sandbox. Configured under **Host Mounts** in the New Run modal.

| Field | Example |
|-------|---------|
| Host path | `/Users/you/datasets` |
| Sandbox path | `/home/agentuser/datasets` |
| Mode | `ro` (read-only) or `rw` (read-write) |

The repo itself is at `/home/agentuser/repo` inside the sandbox. You can mount data directories alongside it.

Certain paths are blocked for security: `/etc`, `/proc`, `/sys`, `/dev`, `/root`, and the sandbox repo root itself.

### MCP servers

Add external tool servers under **MCP Servers** in the New Run modal. JSON format:

```json
{
  "my-server": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": { "GITHUB_TOKEN": "your-token" }
  },
  "my-sse-server": {
    "type": "sse",
    "url": "http://localhost:3000/sse"
  }
}
```

MCP servers give the agent additional tools (database queries, API calls, custom integrations) beyond its built-in capabilities.

## CLI config

Separate from server settings. Stored at `~/.autofyn/config.json`.

```bash
autofyn config get                 # Show CLI config
autofyn config set --api-key KEY   # Set dashboard API key
autofyn config path                # Show path
```

This only affects how the CLI connects to the dashboard API. Server settings (tokens, repo, budget) use `autofyn settings` instead.
