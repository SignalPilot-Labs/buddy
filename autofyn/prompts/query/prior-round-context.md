## Prior-round context

The previous round wrote its reports to `/tmp/round-{PRIOR_ROUND_NUMBER}/`:

- `orchestrator.md` — the orchestrator's narrative: what the round attempted, what shipped, what failed, and what's next. Read this FIRST for quick context.
- `architect.md` — the spec that was planned
- `backend-dev.md` / `frontend-dev.md` — what was built, skipped, or deviated from the spec
- `code-reviewer.md` / `ui-reviewer.md` / `security-reviewer.md` — reviewer verdicts and feedback
- `code-explorer.md` / `debugger.md` — exploration or diagnostic findings

Read whichever are relevant to your current task before producing your own output. Build on what was done — do not repeat it. If you need deeper history, glob `/tmp/round-*/`.
