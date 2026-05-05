<div align="center">

<h1>AutoFyn</h1>

**Run Claude in self-improving loops to optimize measurable goals.**

built the [#1 Spider 2.0 DBT agent](https://github.com/SignalPilot-Labs/SignalPilot) · found 131 vulnerabilities across popular OSS · improved Caveman compression from 44% to 54%

<img src="assets/ui.png" width="800" alt="AutoFyn Monitor" />

<br/>

<img src="assets/autofyn-working.png" width="800" alt="AutoFyn Working" />

</div>

**[Getting Started](docs/user/getting-started.md)** · **[CLI](docs/user/cli.md)** · **[Remote Sandboxes](docs/user/remote-sandboxes.md)** · **[Config](docs/user/config.md)** · **[FAQ](docs/user/faq.md)**

---

Give it a repo, a task, and a time limit. Walk away. Come back to a PR.

Each round runs Claude in a sandboxed Docker container with fresh context. A persistent run state tracks the goal, eval history, and learned rules across rounds — the agent measures progress, learns from failures, and improves instead of degrading.

## Results

### Security audits

- **[Warp](https://www.warp.dev/)** — 30 vulnerabilities (6 Critical, 7 High, 8 Medium, 9 Low), 3 exploit chains. Responsibly disclosed. [CVEs](docs/cves.md#warp)
- **[LiteLLM](https://github.com/BerriAI/litellm)** — 14 vulnerabilities (3 Critical, 4 High, 4 Medium, 3 Low), 2 exploit chains. Responsibly disclosed. [CVEs](docs/cves.md#litellm)
- **[Open WebUI](https://github.com/open-webui/open-webui)** — 12 vulnerabilities (4 Critical, 5 High, 3 Medium), 4 exploit chains. Responsibly disclosed.
- **[Langflow](https://github.com/langflow-ai/langflow)** — 22 vulnerabilities (3 Critical, 13 High, 6 Medium), 4 exploit chains. Responsibly disclosed. [CVEs](docs/cves.md#langflow)
- **[RAGFlow](https://github.com/infiniflow/ragflow)** — 17 vulnerabilities (5 Critical, 11 High, 1 Medium), 5 exploit chains. Responsibly disclosed.
- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — 36 vulnerabilities (13 Critical, 22 High, 1 Medium), 18 exploit chains. Responsibly disclosed.

### Software engineering

- **[SignalPilot](https://github.com/SignalPilot-Labs/SignalPilot)** — built a data analysis agent from scratch, #1 on the [Spider 2.0 dbt benchmark](https://spider2-sql.github.io/).
- **[Caveman](https://github.com/tempcollab/caveman)** — optimized the prompt compression skill by +10% without quality loss ([write-up](https://github.com/tempcollab/caveman/blob/main/docs/improving-caveman-with-autofyn.md)).

## Quick start

```bash
git clone https://github.com/SignalPilot-Labs/AutoFyn.git ~/.autofyn
pip install ~/.autofyn/cli
autofyn update && autofyn start
```

If your agent needs docker access, run

```
autofyn start --allow-docker
```

Two release channels:
- `autofyn update --branch production` — **stable** (recommended)
- `autofyn update --branch main` — **nightly** (latest features)

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

- **State, not context.** Each round gets a clean context window. Cross-round knowledge is a structured `run_state.md`. Context never degrades because it never accumulates.
- **Dense reward signal.** Every round ends with a real eval: run the benchmark, execute the exploit, check the test suite. The score delta is appended to eval history, allowing objective progress monitoring.
- **Policy updates from failures.** Reviewer findings and repeated mistakes become persistent Rules: `ALWAYS: run migrations before tests (because round 4 broke prod, round 4)`. Injected into every subagent's context next round.
- **Honest feedback loop.** Reviewers are independent. A round that improves the metric but violates a constraint is rejected. So, the agent corrects course instead of reinforcing bad decisions.
- **Time-locked episodes.** `end_session` is denied until the budget expires. It iterates toward the target for the full duration.

## CLI reference

```
# Services
autofyn start                          # start services
autofyn start --allow-docker           # start with Docker access for sandbox
autofyn stop                           # stop all services
autofyn update                         # pull latest code + images
autofyn update --branch main           # switch to nightly channel
autofyn update --image-tag abc1234     # pin to a specific version
autofyn update --build                 # force local build (for dev)
autofyn logs                           # stream container logs
autofyn kill                           # remove all containers
autofyn uninstall                      # remove everything (containers, images, ~/.autofyn)

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

## Remote sandboxes

Runs can execute on remote machines (HPC clusters, GPU servers) instead of local Docker. AutoFyn SSH-tunnels to the remote, streams logs back, and manages the lifecycle automatically.

See [docs/user/remote-sandboxes.md](docs/user/remote-sandboxes.md) for setup, start command examples, GPU access, and troubleshooting.

## Responsible disclosure

All vulnerabilities were privately disclosed to maintainers before any public mention. Full reports are withheld until patches are available.

---

Built with the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk). Apache 2.0 License.
