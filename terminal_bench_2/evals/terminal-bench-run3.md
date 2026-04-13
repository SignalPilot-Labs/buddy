# Terminal-Bench Run 3 — AutoFyn vs claude-opus-4-6 (post-nerf)

## Goal

Re-run of the modified task set with `claude-opus-4-6` to compare directly against Run 2 (same tasks, same setup, different model). Run 2 used `claude-opus-4-5` and scored 48.2%. This run tests whether the newer model does better.

## Changes from Run 2

| Change | Run 2 | Run 3 |
|--------|-------|-------|
| Model | claude-opus-4-5 | claude-opus-4-6 |
| Everything else | — | identical |

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

## Results

**Job:** `jobs-run3/2026-04-10__16-08-48`
**Trials:** 56 scored, 8 errors — **Mean score: 0.328** (21/64 total, 21/56 on 14 tasks)

| Task | Score | Errors |
|------|-------|--------|
| fix-git | 4/4 (100%) | — |
| cobol-modernization | 4/4 (100%) | 1x AgentTimeoutError¹ |
| regex-log | 4/4 (100%) | — |
| sqlite-db-truncate | 4/4 (100%) | — |
| overfull-hbox | 2/4 (50%) | — |
| cancel-async-tasks | 2/4 (50%) | — |
| write-compressor | 1/4 (25%) | 3x AgentTimeoutError¹ |
| filter-js-from-html | 0/4 (0%) | — |
| raman-fitting | 0/4 (0%) | 2x AgentTimeoutError |
| prove-plus-comm | 0/4 (0%) | 4x NonZeroAgentExitCodeError |
| mteb-retrieve | 0/4 (0%) | 4x AgentTimeoutError |
| dna-assembly | 0/4 (0%) | 4x AgentTimeoutError |
| gpt2-codegolf | 0/4 (0%) | 4x AgentTimeoutError |
| fix-code-vulnerability | 0/4 (0%) | 4x AgentTimeoutError |
| hello-world | — | 4x RewardFileNotFoundError |
| hello-world-2 | — | 4x RewardFileNotFoundError |

### Error Types
- **AgentTimeoutError (22)** — significantly more timeouts than Run 2 (17). Tasks that passed in Run 2 (`dna-assembly` 3/4, `raman-fitting` 1/4) timed out on all trials here.
- **NonZeroAgentExitCodeError (4)** — `prove-plus-comm` crashed on all 4 trials, same as Run 2.
- **RewardFileNotFoundError (8)** — hello-world smoke tests, excluded from score.

### Notes
- **opus-4-6 scored lower than opus-4-5** on the same tasks: 37.5% vs 48.2% in Run 2. The expected newer-model advantage did not materialise.
- The most likely explanation is a **model regression**: Anthropic appears to have updated `claude-opus-4-6` in the 2nd week of April, degrading its coding performance. The model was slower and timed out on tasks (`dna-assembly`, `raman-fitting`) that opus-4-5 handled comfortably within the same timeouts.
- `write-compressor` dropped from 3/4 (Run 2) to 1/4, and `cancel-async-tasks` from 3/4 to 2/4. Both regressions are consistent with a slower, less capable model version hitting timeouts.
- Run 4 reverts to `claude-opus-4-5` and adds the caveman strategy.

¹ Agent timed out but had already produced a correct solution; verifier scored it 1.0.
