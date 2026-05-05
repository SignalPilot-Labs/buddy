# CLI Reference

All commands support `--json` for machine-readable output and `-h` for help.

## Services

```bash
autofyn start                      # Start all services (docker compose up)
autofyn start --allow-docker       # Mount Docker socket into sandbox (unsafe)
autofyn stop                       # Stop all containers
autofyn update                     # Pull latest code + images
autofyn update --branch main       # Switch to nightly channel
autofyn update --branch production # Switch to stable channel
autofyn update --image-tag abc123  # Pin to specific image version
autofyn update --build             # Force local build (for development)
autofyn logs                       # Stream container logs (tail 100 + follow)
autofyn logs 50                    # Tail last 50 lines + follow
autofyn kill                       # Remove all containers (asks confirmation)
autofyn uninstall                  # Remove everything: containers, images, ~/.autofyn
```

### `autofyn start`

Starts the connector process (handles SSH tunnels for remote sandboxes), then runs `docker compose up -d`. On first run, it auto-detects Claude and GitHub tokens from your local CLI tools (`claude setup-token`, `gh auth token`).

`--allow-docker` mounts the host Docker socket into sandbox containers. The agent can then create/inspect/remove any container on the host. Only use this if your task requires Docker access.

### `autofyn update`

Pulls latest git changes and maps your branch to an image tag:

| Branch       | Image tag |
|-------------|-----------|
| `production` | `stable`  |
| `main`       | `nightly` |
| other        | builds locally |

Always run `autofyn update --build` then `autofyn start` after code changes during development.

## Runs

```bash
autofyn run                        # Interactive run selector (TUI)
autofyn run new -p "Fix bugs"      # Start a new run
autofyn run new -p "Add tests" -d 60 -b 5.00 --base-branch develop
autofyn run list                   # List recent runs
autofyn run list -r owner/repo     # Filter by repo
autofyn run get <run_id>           # Run details + action menu
```

### `autofyn run new` flags

| Flag | Default | Description |
|------|---------|-------------|
| `-p, --prompt` | (required) | Task description |
| `-b, --budget` | `0` (unlimited) | Max spend in USD |
| `-d, --duration` | `0` (no lock) | Minutes the agent must work |
| `--base-branch` | `main` | Branch to base work on |

### `autofyn run` (no subcommand)

Opens an interactive TUI with a scrollable list of runs. Select a run to see details and an action menu: pause, resume, stop, inject prompt, stream events, view diff, view audit log.

## Settings

```bash
autofyn settings status            # Check which credentials are configured
autofyn settings get               # Show all settings (secrets masked)
autofyn settings set --claude-token TOKEN
autofyn settings set --git-token TOKEN
autofyn settings set --github-repo owner/repo
autofyn settings set --budget 10.00
autofyn settings set --api-key SECRET
```

Claude tokens are added to a **token pool** — you can add multiple tokens and AutoFyn rotates through them to avoid rate limits.

## Repos

```bash
autofyn repos list                 # List repos + run counts
autofyn repos detect               # Detect git repo in current directory
autofyn repos set-active owner/repo
autofyn repos remove owner/repo
```

AutoFyn auto-detects the repo from your local git remote. If it finds one that isn't configured, it offers to add it.

## CLI Config

```bash
autofyn config get                 # Show CLI config
autofyn config set --api-key KEY   # Set dashboard API key
autofyn config path                # Show config file path (~/.autofyn/config.json)
```

This configures the CLI itself (API URL, API key). Server settings (tokens, repo, budget) use `autofyn settings` instead.

## Global flags

| Flag | Description |
|------|-------------|
| `--json` | Output raw JSON instead of formatted tables |
| `--api-url URL` | Override dashboard API base URL |
| `--api-key KEY` | Override dashboard API key |
