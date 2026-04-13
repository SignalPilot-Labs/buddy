# Terminal-Bench Run 1 — AutoFyn vs claude-opus-4-6

## What is this?

**Terminal-Bench 2** is a benchmark of real-world software engineering tasks. Each task gives an AI agent a coding challenge inside an isolated Linux container and scores it on whether automated tests pass.

**AutoFyn** is our AI agent — it uses Claude Opus 4.6 as the brain, orchestrating multiple specialized subagents (planner, builder, reviewer, explorer) to tackle each task.

Each task was run **4 times** (trials) to get a reliable score. Scoring is binary: 1 if all tests pass, 0 otherwise.

## Tasks (14 total, 4 trials each)

| Task | Difficulty¹ | Agent Timeout² | Expert Time³ |
|------|------------|---------------|-------------|
| fix-git | easy | 15 min | 5 min |
| cobol-modernization | easy | 15 min | 20 min |
| overfull-hbox | easy | 12 min | 60 min |
| prove-plus-comm | easy | 15 min | 5 min |
| filter-js-from-html | medium | 30 min | 45 min |
| raman-fitting | medium | 15 min | 5 min |
| mteb-retrieve | medium | 30 min | 15 min |
| regex-log | medium | 15 min | 45 min |
| sqlite-db-truncate | medium | 15 min | 60 min |
| video-processing | hard | 60 min | 400 min |
| dna-assembly | hard | 30 min | 60 min |
| gpt2-codegolf | hard | 15 min | 2400 min |
| train-fasttext | hard | 60 min | 30 min |
| sam-cell-seg | hard | 120 min | 600 min |

¹ **Difficulty** — set by the task author, based on how hard the problem is for a human engineer.

² **Agent Timeout** — the maximum time the AI agent is allowed to work on the task. If it hasn't solved it by then, the trial is marked as failed. Harder tasks get more time.

³ **Expert Time** — how long a skilled human engineer would take to solve the same task from scratch. A task with 2400 min expert time (like `gpt2-codegolf`) is a 40-hour problem for a human — essentially a multi-day research challenge.

## Results

**Job:** `jobs/2026-04-09__19-53-48`
**Trials:** 41 completed, 24 errors — **Mean score: 0.321** (18/41 passed)

| Task | Score | Errors |
|------|-------|--------|
| fix-git | 4/4 (100%) | — |
| cobol-modernization | 4/4 (100%) | — |
| regex-log | 4/4 (100%) | — |
| sqlite-db-truncate | 3/3 (100%) | 1x DaytonaError |
| overfull-hbox | 2/2 (100%) | 2x DaytonaError |
| dna-assembly | 1/1 (100%) | 3x DaytonaError |
| filter-js-from-html | 0/4 (0%) | — |
| raman-fitting | 0/2 (0%) | 1x AgentTimeoutError, 1x DaytonaError |
| sam-cell-seg | 0/4 (0%) | — |
| video-processing | 0/4 (0%) | — |
| gpt2-codegolf | — | 1x AgentTimeoutError, 3x DaytonaError |
| mteb-retrieve | — | 4x AgentTimeoutError |
| prove-plus-comm | — | 3x NonZeroAgentExitCodeError, 1x DaytonaError |
| train-fasttext | — | 4x NonZeroAgentExitCodeError |

### Error Types
- **DaytonaError (11)** — the cloud sandbox (Daytona) failed to start, due to running 3 tasks in parallel hitting the disk limit. Infrastructure issue, not agent failure. In subsequent runs, Daytona's resource limits were increased to fix this.
- **AgentTimeoutError (6)** — the agent ran out of time before solving the task. Could be the task is too hard, or sandbox startup overhead ate into the budget.
- **NonZeroAgentExitCodeError (7)** — the Claude CLI process crashed inside the container. Infrastructure issue, being investigated.

### Notes
- Tasks that scored 0/4 cleanly (`filter-js-from-html`, `video-processing`, `sam-cell-seg`) ran without errors — the agent just didn't produce a correct solution. These are genuine agent quality failures.
- 15 of the 24 errors are infrastructure issues (DaytonaError + NonZeroExit), not the agent failing at the task itself. Run 2 retries those with reduced concurrency.
