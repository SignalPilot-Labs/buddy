# Hold-Out Tasks

These 3 tasks are reserved for final validation only. NO experiments run on them.

```
HOLD-OUT TASKS:
1. gpt2-codegolf      — pure timeout/unsolvable (hard, 0% all runs)
2. dna-assembly        — inconsistent, model-sensitive (hard, 0-100% across runs)
3. cancel-async-tasks  — moderate inconsistency (hard, 50-75%)
```

## Selection Rationale

- **gpt2-codegolf** covers the "unsolvable under budget" failure mode. If a change improves this, it's likely a fundamental efficiency win. If it regresses, we've added overhead.
- **dna-assembly** covers model sensitivity and caveman overhead regression. It went from 75% (run2, no caveman) to 50% (run4, caveman). Serves as a canary for overhead changes.
- **cancel-async-tasks** covers moderate inconsistency (75% baseline in run4). Tests whether changes maintain reliability on tasks that already mostly work.

Together they span: always-fail, sometimes-fail, usually-pass — across easy/medium/hard difficulty.
