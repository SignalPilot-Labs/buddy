<div align="center">

```
     ____   __  __  ____   ____   __  __
    / __ ) / / / / / __ \ / __ \ / / / /
   / __  |/ / / / / / / // / / // /_/ /
  / /_/ // /_/ / / /_/ // /_/ //  __  /
 /_____/ \____/ /_____//_____//_/  /_/
```

# buddy

**your autonomous coding agent. give it a repo, get back a PR.**

</div>

---

```
$ buddy start --repo your-org/your-repo --task "refactor auth module" --hours 4

  starting session abc123...
  [10:00] exploring codebase...
  [10:01] planning: found 3 improvement areas
  [10:04] writing: auth/session.py refactored
  [10:04] git commit: "refactor: extract session validation into SessionManager"
  [10:07] writing: auth/middleware.py updated
  [10:07] git commit: "refactor: simplify auth middleware, remove dead code"
  [10:11] reviewing own work... looks good
  [10:14] writing: tests/test_auth.py added
  [10:14] git commit: "test: add coverage for SessionManager edge cases"
  ...4 hours later...
  [14:00] time's up. opening pull request...

  PR opened: github.com/your-org/your-repo/pull/47
  "Refactor auth module — 12 commits, 340 lines changed"

$ # go review and merge
```

---

## What it does

**Set it and forget it** — Point it at a repo, describe what you want (or let it find improvements on its own), set a duration from 30 minutes to 8 hours, and walk away.

**Watch everything live** — A real-time browser dashboard shows every file edit, tool call, and commit as it happens. Nothing is hidden.

**Stay in control** — Pause mid-run, inject new instructions, redirect its focus, or stop it cleanly at any moment. You're never locked out.

**Time-lock sessions** — Lock the agent for hours so it keeps iterating instead of declaring "done" after the first pass. Great for overnight runs and deep refactors.

**Clean git history** — One logical commit per change, pushed immediately as it works. The PR tells a readable story — not a single monster commit.

**Safe execution** — Any code it runs executes inside Firecracker microVMs or gVisor sandboxes, never on your host machine.

**Budget caps** — Set a max USD spend per run so it can't burn through your API credits while you sleep.

---

## Quick start

```bash
cp buddy/.env.example .env  # add your tokens
docker compose up --build -d
# open http://localhost:3400
```

Three env vars required:

- `CLAUDE_CODE_OAUTH_TOKEN` — your Anthropic token
- `GIT_TOKEN` — a GitHub personal access token with repo scope
- `GITHUB_REPO` — target repo in `owner/repo` format

That's it. Everything else runs in Docker on your machine — no SaaS, no cloud dependency.

---

## How it works

1. You start a run from the dashboard — pick a repo, describe the task, set a time limit
2. Buddy explores your codebase — reads files, understands structure, finds where to act
3. It plans, codes, reviews its own work, and commits — in a loop, for as long as you gave it
4. When time's up (or you stop it), it opens a pull request with everything it did
5. You review and merge — or don't. You're in charge.

---

Built with the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk), Next.js, and Docker.

MIT License
