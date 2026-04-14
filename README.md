<div align="center">

<h1>autofyn</h1>

**autonomous AI coder that gets better the longer it runs.**

<img src="assets/ui.png" width="800" alt="AutoFyn Monitor" />

<br/>

<img src="assets/autofyn-working.png" width="800" alt="AutoFyn Working" />

</div>

---

AutoFyn is an autonomous AI agent loop that runs Claude inside sandboxed Docker containers, round after round, until the job is done. Each round is a fresh Claude session with clean context. Memory persists across rounds via git history, round reports, and an accumulating lessons file — so the agent learns from its own mistakes mid-run.

Give it a repo, a task, and a time limit. Walk away. Come back to a PR.

## Quick start

```bash
git clone https://github.com/SignalPilot-Labs/AutoFyn.git
cd autofyn && ./install.sh             # installs CLI + builds Docker images
autofyn start                          # auto-detects tokens from claude/gh CLI
```

Open [http://localhost:3400](http://localhost:3400) for the dashboard.

On first start, AutoFyn will auto-detect your Claude token (via `claude setup-token`) and GitHub token (via `gh auth token`), and detect the repo from your local git remote. You can also configure manually:

```bash
autofyn settings set --claude-token YOUR_ANTHROPIC_KEY --git-token YOUR_GITHUB_TOKEN --github-repo owner/repo
```

To update an existing install: `autofyn update`

### Run

```bash
autofyn run new -p "Fix authentication bugs" -d 30
```

If you're inside a git repo, autofyn auto-detects it — no need to specify `--github-repo`:

```bash
cd your-project/
autofyn run new -p "Fix authentication bugs" -d 30
```

### Monitor

Use the CLI or open [http://localhost:3400](http://localhost:3400).

```bash
autofyn run                            # interactive run selector
autofyn run get <run_id>               # run details + action menu
```

## CLI reference

```
# Services
autofyn start                          # start services (fast, no rebuild)
autofyn start --allow-docker           # start with Docker access for sandbox (unsafe)
autofyn stop                           # stop all services
autofyn update                         # pull latest code + rebuild images
autofyn logs                           # stream all container logs (Ctrl+C to stop)
autofyn logs 50                        # tail last 50 lines + follow
autofyn kill                           # remove all containers

# Runs
autofyn run                            # interactive run selector
autofyn run new -p "Fix auth bugs"     # start a new run
autofyn run list                       # list recent runs
autofyn run get <run_id>               # show run details + action menu

# Settings & config
autofyn settings status                # check credential config
autofyn settings get                   # show all settings (masked)
autofyn settings set --claude-token TOKEN --git-token TOKEN --github-repo owner/repo

# Repos (auto-detects local git repo)
autofyn repos list                     # list repos with run counts
autofyn repos detect                   # detect git repo in current directory
autofyn repos set-active owner/repo    # set active repo
autofyn repos remove owner/repo        # remove a repo

# Agent
autofyn agent health                   # check agent status
autofyn agent branches                 # list git branches

# CLI config
autofyn config get                     # show CLI config
autofyn config set --api-key KEY       # update CLI config
```

Use `--json` on any command for machine-readable output.

### Docker access

By default, sandboxes cannot use Docker. If your task requires the agent to build images or manage containers, start with `--allow-docker`:

```bash
autofyn start --allow-docker
```

This mounts the host Docker socket into sandbox containers, giving the agent full Docker daemon access. Only use this if you trust the prompts you send — the agent can create, inspect, and remove any container on the host.

---

Built with the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk). MIT License.
