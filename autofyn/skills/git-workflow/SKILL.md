---
description: "Use when committing code, pushing branches, writing .gitignore entries, or generating PR metadata. Covers commit format, branch rules, and artifact exclusion."
---

# Git Workflow

## Commit Format

```
[Round N] <imperative description>
```

Examples:
- `[Round 1] Add user authentication API`
- `[Round 2] Fix N+1 query in dashboard endpoint`
- `[Round 3] Refactor session manager into separate modules`

## Branch Rules

- You are already on the correct working branch. Never create or switch branches.
- Only the orchestrator commits and pushes. Subagents must not run git write commands.
- Push after every commit: `git push origin HEAD`.
- Do NOT create the actual PR — it is created automatically.


## Before Committing

Run `git status` and check for build artifacts. These must NOT be committed:

```
node_modules/   .next/        __pycache__/   *.pyc
dist/           .cache/       build/         *.log
.env            .env.local    *.sqlite       coverage/
```

If `.gitignore` doesn't cover them, add the entries before committing.

## PR Metadata

When the session is ending, generate `/tmp/pr.json` from `git log --oneline` and `git diff --stat`:

```json
{"title": "Short imperative title", "description": "## Summary\n- what and why\n\n## Tests\n- what was tested"}
```