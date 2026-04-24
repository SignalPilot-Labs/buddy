<div align="center">

<h1>autofyn</h1>

**Runs Claude in self-improving loops that work on real codebases.**

built the [#1 Spider 2.0 DBT agent](https://github.com/SignalPilot-Labs/SignalPilot) · found 26 vulnerabilities across LiteLLM and Open WebUI · improved Caveman compression from 44% to 54%

<img src="assets/ui.png" width="800" alt="AutoFyn Monitor" />

<br/>

<img src="assets/autofyn-working.png" width="800" alt="AutoFyn Working" />

</div>

---

Give it a repo, a task, and a time limit. Walk away. Come back to a PR.

Each round runs Claude in a sandboxed Docker container with fresh context. A persistent run state tracks the goal, eval history, and learned rules across rounds — the agent measures progress, learns from failures, and improves instead of degrading.

## How it works

Most AI coding agents run Claude in a single long context or a naive bash loop — dump progress to a file, read it back, repeat. They have no structured memory across iterations, no measurement of whether they're improving, and no mechanism to stop repeating mistakes. Context degrades, errors compound, and the agent drifts.

AutoFyn takes a different approach, inspired by reinforcement learning:

**State.** Each round starts fresh with a persistent `run_state.md` that carries the goal, eval history, and learned rules across rounds. This is the agent's memory — not a chat log, but a structured representation of what it knows.

**Reward signal.** Every round ends with a measurable eval: run the benchmark, count the vulnerabilities, check the test suite. The result is appended to an eval history with trend annotations (IMPROVED, PLATEAU, REGRESSION, BREAKTHROUGH). The agent sees whether it's making progress or going in circles.

**Policy updates.** When reviewers find patterns — a recurring mistake, a repo quirk, a constraint violation — the orchestrator promotes them to Rules: `ALWAYS/NEVER: <action> (because <reason>, round N)`. These persist across rounds and are injected into every subagent's context. The agent learns from its failures and doesn't repeat them.

**Explore → Plan → Build → Review.** Each round follows a fixed pipeline. Specialized subagents handle each phase — an architect designs, a builder implements, reviewers verify. The orchestrator delegates but never writes code itself. Reviewers are independent: they get file paths, not instructions on what to approve, so they function as an unbiased feedback loop.

**Time-locked sessions.** The agent can't declare victory early. `end_session` is denied until the time limit, forcing the agent to keep iterating. Combined with eval history, this means the agent spends its budget on measurable improvement rather than premature PRs.

The result: an agent that measures, learns, and improves over rounds instead of degrading. Each round builds on the last — not by carrying forward a growing context window, but by carrying forward structured knowledge about what works.

## Results

### Security audits

- **[LiteLLM](https://github.com/BerriAI/litellm)** — 14 vulnerabilities (3 Critical, 4 High, 4 Medium, 3 Low), 2 exploit chains. Responsibly disclosed.
- **[Open WebUI](https://github.com/open-webui/open-webui)** — 12 vulnerabilities (4 Critical, 5 High, 3 Medium), 4 exploit chains. Responsibly disclosed.

### Software engineering

- **[SignalPilot](https://github.com/SignalPilot-Labs/SignalPilot)** — built a data analysis agent from scratch, #1 on the [Spider 2.0 dbt benchmark](https://spider2-sql.github.io/).
- **[Caveman](https://github.com/tempcollab/caveman)** — optimized the prompt compression skill by +10% without quality loss ([write-up](https://github.com/tempcollab/caveman/blob/main/docs/improving-caveman-with-autofyn.md)).

## Quick start

```bash
git clone https://github.com/SignalPilot-Labs/AutoFyn.git
cd autofyn && ./install.sh
autofyn start
```

Open [localhost:3400](http://localhost:3400) for the dashboard. AutoFyn auto-detects your Claude token, GitHub token, and repo from your local git remote.

Pick a starter preset — **Security hardening**, **Bug sweep**, **Code quality**, or **Test coverage** — or write your own goal:

```bash
autofyn run new -p "Optimize the algorithm to hit 60% compression ratio without further quality loss" -d 120
```

To configure manually:

```bash
autofyn settings set --claude-token YOUR_KEY --git-token YOUR_TOKEN --github-repo owner/repo
```

## CLI reference

```
# Services
autofyn start                          # start services
autofyn start --allow-docker           # start with Docker access for sandbox
autofyn stop                           # stop all services
autofyn update                         # pull latest + rebuild
autofyn logs                           # stream container logs
autofyn kill                           # remove all containers

# Runs
autofyn run                            # interactive run selector
autofyn run new -p "Fix auth bugs"     # start a new run
autofyn run list                       # list recent runs
autofyn run get <run_id>               # run details + action menu

# Settings
autofyn settings status                # check config
autofyn settings get                   # show all settings
autofyn settings set --claude-token TOKEN --git-token TOKEN --github-repo owner/repo

# Repos
autofyn repos list                     # list repos
autofyn repos set-active owner/repo    # set active repo
```

Use `--json` on any command for machine-readable output.

## Responsible disclosure

All vulnerabilities were privately disclosed to maintainers before any public mention. Full reports are withheld until patches are available.

---

Built with the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk). MIT License.
