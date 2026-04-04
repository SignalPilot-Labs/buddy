<div align="center">

<h1>buddy</h1>

**autonomous coding agent. give it a repo, get back a PR.**

long-running sessions · sandboxed execution · live supervision

<img src="assets/ui.png" width="800" alt="Buddy Monitor" />

<br/>

<img src="assets/buddy-working.png" width="800" alt="Buddy Working" />

</div>

---

Set a task, set a time limit, walk away. Run it for 30 minutes or 8+ hours — it plans, builds, reviews, and commits until the clock runs out. Code executes in isolated Sandboxes and never on your machine.

## Quick start

```bash
git clone https://github.com/SignalPilot-Labs/buddy.git
cd buddy && ./install.sh             # installs CLI + builds Docker images + starts services
buddy settings set \
  --claude-token YOUR_ANTHROPIC_KEY \
  --git-token YOUR_GITHUB_TOKEN \
  --github-repo owner/repo
```

To update an existing install: `buddy update`

### Run

```bash
buddy run new -p "Fix authentication bugs" -d 30
```

If you're inside a git repo, buddy auto-detects it — no need to specify `--github-repo`:

```bash
cd your-project/
buddy run new -p "Fix authentication bugs" -d 30
```

### Monitor

Use the CLI or open [http://localhost:3400](http://localhost:3400).

```bash
buddy run                            # interactive run selector
buddy run get <run_id>               # run details + action menu
```

## CLI reference

```
# Services
buddy install                        # first-time setup: build images + start
buddy start                          # start services (fast, no rebuild)
buddy stop                           # stop all services
buddy update                         # pull latest code + rebuild images
buddy kill                           # remove all containers

# Runs
buddy run                            # interactive run selector
buddy run new -p "Fix auth bugs"     # start a new run
buddy run list                       # list recent runs
buddy run get <run_id>               # show run details + action menu

# Settings & config
buddy settings status                # check credential config
buddy settings get                   # show all settings (masked)
buddy settings set --claude-token TOKEN --git-token TOKEN --github-repo owner/repo

# Repos (auto-detects local git repo)
buddy repos list                     # list repos with run counts
buddy repos detect                   # detect git repo in current directory
buddy repos set-active owner/repo    # set active repo
buddy repos remove owner/repo        # remove a repo

# Agent
buddy agent health                   # check agent status
buddy agent branches                 # list git branches

# CLI config
buddy config get                     # show CLI config
buddy config set --api-key KEY       # update CLI config
```

Use `--json` on any command for machine-readable output.

---

Built with the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk). MIT License.
