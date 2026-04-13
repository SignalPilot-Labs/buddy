# Terminal-Bench Run 4 — AutoFyn + Caveman token strategy

## Goal

Same task set as Run 2/3, with two changes: (1) added the **caveman token save strategy** — the caveman plugin's `SKILL.md` is injected into the orchestrator system prompt and all subagent prompts, teaching the agent to checkpoint progress to disk rather than relying on context state; (2) added `hello-world` and `hello-world-2` as smoke-test tasks. Reverts to `claude-opus-4-5` after Run 3 exposed a regression in `claude-opus-4-6`.

## Changes from Run 3

| Change | Run 3 | Run 4 |
|--------|-------|-------|
| Model | claude-opus-4-6 | claude-opus-4-5 |
| Caveman skill | not injected | injected into system + subagent prompts |
| hello-world tasks | not included | added (smoke test) |
| Total trials | 56 | 64 |

## Tasks (16 total, 4 trials each = 64 trials)

| Task | Difficulty | Agent Timeout | Expert Time |
|------|-----------|--------------|-------------|
| fix-git | easy | 15 min | 5 min |
| cobol-modernization | easy | 15 min | 20 min |
| overfull-hbox | easy | 12 min | 60 min |
| prove-plus-comm | easy | 15 min | 5 min |
| hello-world | easy | — | — |
| hello-world-2 | easy | — | — |
| filter-js-from-html | medium | 30 min | 45 min |
| raman-fitting | medium | 15 min | 5 min |
| mteb-retrieve | medium | 30 min | 15 min |
| regex-log | medium | 15 min | 45 min |
| sqlite-db-truncate | medium | 15 min | 60 min |
| dna-assembly | hard | 30 min | 60 min |
| gpt2-codegolf | hard | 15 min | 2400 min |
| fix-code-vulnerability | hard | 15 min | — |
| write-compressor | hard | 15 min | — |
| cancel-async-tasks | hard | 15 min | — |

## Run Command

```bash
DAYTONA_API_KEY=<key> CLAUDE_CODE_OAUTH_TOKEN=<token> harbor run \
  --agent-import-path terminal_bench.agent:AutoFynAgent \
  --model anthropic/claude-opus-4-5 \
  --path tasks-run2 \
  --env daytona \
  -k 4 -n 24 -y
```

## Results

**Job:** `jobs-run4/2026-04-10__18-02-13`
**Trials:** 64 total, 25 errors — **Mean score: 0.4375** (28/64 passed)

| Task | Score | Errors |
|------|-------|--------|
| fix-git | 4/4 (100%) | — |
| cobol-modernization | 4/4 (100%) | — |
| regex-log | 4/4 (100%) | — |
| sqlite-db-truncate | 4/4 (100%) | — |
| prove-plus-comm | 4/4 (100%) | — |
| cancel-async-tasks | 3/4 (75%) | — |
| overfull-hbox | 2/4 (50%) | — |
| dna-assembly | 2/4 (50%) | — |
| raman-fitting | 1/4 (25%) | — |
| filter-js-from-html | 0/4 (0%) | — |
| gpt2-codegolf | 0/4 (0%) | 4x AgentTimeoutError |
| mteb-retrieve | 0/4 (0%) | 4x AgentTimeoutError |
| write-compressor | 0/4 (0%) | 4x AgentTimeoutError |
| fix-code-vulnerability | 0/4 (0%) | 4x AgentTimeoutError |
| hello-world | — | 4x RewardFileNotFoundError |
| hello-world-2 | — | 4x RewardFileNotFoundError |

### Error Types
- **AgentTimeoutError (17)** — agent ran out of time. Same tasks as Run 2 (gpt2-codegolf, mteb-retrieve, write-compressor, fix-code-vulnerability) plus one overfull-hbox trial.
- **RewardFileNotFoundError (8)** — hello-world tasks: the verifier reward file was not produced. Infrastructure issue with the new tasks, not an agent failure.

### Notes
- **prove-plus-comm** was the biggest gain over Run 2: 4/4 vs 0/4. In Run 2 all four trials crashed with `NonZeroAgentExitCodeError` before doing any work; caveman resolved that entirely.
- **write-compressor** regressed: 0/4 here vs 2/4 in Run 2. The caveman overhead appears to hurt on compute-heavy tasks where the timeout is already tight.
- **Overall cost dropped 15.8%** ($47.76 vs $56.70) despite a higher score — caveman helps the agent stay focused and avoid redundant work.
- hello-world tasks need a verifier fix before they can be scored; excluding them the mean over the 14 original tasks is **28/56 = 0.500**.
