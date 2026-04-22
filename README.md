<div align="center">

<h1>autofyn</h1>

**autonomous AI engineer that improves the longer it runs.**

built the [#1 Spider 2.0 dbt agent](https://spider2.yale.edu) · found 26 vulnerabilities across LiteLLM and Open WebUI · optimized Caveman to +54% compression

<img src="assets/ui.png" width="800" alt="AutoFyn Monitor" />

<br/>

<img src="assets/autofyn-working.png" width="800" alt="AutoFyn Working" />

</div>

---

AutoFyn runs Claude in iterative rounds inside sandboxed Docker containers. Each round is a fresh session with clean context. Memory persists across rounds via git history, round reports, and a lessons file — so it learns from its own mistakes and builds on what worked.

## Results

| Project | What AutoFyn did | Outcome |
|---|---|---|
| [SignalPilot](https://github.com/SignalPilot-Labs/SignalPilot) | Built a data analysis agent from scratch | #1 on [Spider 2.0 dbt benchmark](https://spider2.yale.edu) |
| [Open WebUI](https://github.com/open-webui/open-webui) | Autonomous security audit | 12 vulnerabilities — 4 Critical, 5 High, 3 Medium, 4 exploit chains |
| [LiteLLM](https://github.com/BerriAI/litellm) | Autonomous security audit | 14 vulnerabilities — critical unauthorized access chain, high privilege escalation chain |
| [Caveman](https://github.com/tempcollab/caveman) | Prompt optimization | +10% compression without quality loss ([write-up](caveman_reddit.md)) |

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
