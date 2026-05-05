# Getting Started

## Install

```bash
git clone https://github.com/SignalPilot-Labs/AutoFyn.git ~/.autofyn
pip install ~/.autofyn/cli
```

## Update and start

```bash
autofyn update && autofyn start
```

`autofyn update` pulls the latest code and Docker images. Two release channels:

- `autofyn update --branch production` — **stable** (recommended)
- `autofyn update --branch main` — **nightly** (latest features)

On first start, AutoFyn will:

1. Auto-detect your Claude token from `claude setup-token` (opens browser OAuth)
2. Auto-detect your GitHub token from `gh auth token`
3. Auto-detect the repo from your local git remote

If auto-detection doesn't work, set them manually:

```bash
autofyn settings set --claude-token YOUR_TOKEN --git-token ghp_YOUR_TOKEN --github-repo owner/repo
```

## Open the dashboard

Go to [localhost:3400](http://localhost:3400). You'll see the run feed — empty for now.

## Start your first run

Click **New Run** in the dashboard. You'll see:

- **Branch picker** — which branch to base work on (default: `main`)
- **Quick Start presets** — one-click tasks: Security hardening, Bug bash, Code quality, Test coverage
- **Custom Prompt** — write your own goal (e.g. "Optimize the algorithm to hit 60% compression ratio")
- **Session Duration** — how long the agent must work before it's allowed to stop. "No lock" lets it end anytime.

Click **New Run** at the bottom. The agent will:

1. Spin up a sandboxed Docker container
2. Clone your repo into it
3. Run rounds of explore → plan → build → review
4. Commit changes and create a PR when done

You can also start runs from the CLI:

```bash
autofyn run new -p "Fix auth bugs" -d 30
```

## What happens during a run

The dashboard shows a live feed of everything the agent does: file reads, edits, bash commands, thinking, and milestone events. The agent works in **rounds** — each round gets fresh context but inherits a persistent `run_state.md` that tracks progress, rules, and eval history.

You can:

- **Inject a prompt** — send a message to the agent mid-run
- **Pause / Resume** — temporarily halt the agent
- **Stop** — end the run and create a PR with whatever changes exist
- **Kill** — terminate immediately without cleanup

## After a run

When the run completes, check the PR on GitHub. The agent creates a branch like `autofyn/fix-abc123` and opens a PR against your base branch.

To see past runs:

```bash
autofyn run list
autofyn run          # interactive selector
```

## Next steps

- [CLI Reference](cli.md) — all commands and flags
- [Configuration](config.md) — config files, env vars, mounts, MCP servers
- [Remote Sandboxes](remote-sandboxes.md) — run on HPC clusters or remote Docker
- [FAQ](faq.md) — common questions and recipes
