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

## How it works

LLM agents that run in a loop hit three failure modes: context grows until the model loses track, mistakes repeat because nothing is learned between iterations, and the agent can't tell whether it's making progress or going in circles. AutoFyn's round loop addresses each one, borrowing from how RL agents learn.

- **State, not context.** Each round gets a clean context window. Cross-round knowledge is a structured `run_state.md` — the goal, eval history, and learned rules — not a growing chat log. The agent reads state, acts, writes state back. Context never degrades because it never accumulates.
- **Dense reward signal.** Every round ends with a real eval: run the benchmark, execute the exploit, check the test suite. The score delta is appended to eval history with trend annotations (IMPROVED, PLATEAU, REGRESSION, BREAKTHROUGH). The agent knows whether it's converging or drifting — and so do you.
- **Policy updates from failures.** Reviewer findings and repeated mistakes become persistent Rules: `ALWAYS: run migrations before tests (because round 4 broke prod, round 4)`. Injected into every subagent's context next round. The same mistake doesn't happen twice because the lesson is encoded in state, not hoped to survive in context.
- **Honest feedback loop.** Reviewers are independent — they receive file paths, not the orchestrator's intent. A round that improves the metric but violates a constraint is rejected. The signal is unbiased, so the agent corrects course instead of reinforcing bad decisions.
- **Time-locked episodes.** `end_session` is denied until the budget expires. The agent can't ship a half-done PR at round 2. It iterates toward the target for the full duration, with eval history telling it what's working.

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
