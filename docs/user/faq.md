# FAQ

## How do I give the agent access to private APIs?

Add environment variables in the **New Run** modal under **Environment Variables**:

```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgres://user:pass@host:5432/db
```

These are encrypted and injected into the sandbox at runtime. They never appear in container env, SSH args, or logs.

## How do I mount local data into the sandbox?

In the **New Run** modal, expand **Host Mounts** and add entries:

- **Host**: `/Users/you/datasets`
- **Sandbox**: `/home/agentuser/datasets`
- **Mode**: `ro` (read-only) or `rw`

The repo is at `/home/agentuser/repo` inside the sandbox. Mount data directories alongside it.

## How do I add MCP tool servers?

In the **New Run** modal, expand **MCP Servers** and paste JSON:

```json
{
  "github": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": { "GITHUB_TOKEN": "ghp_..." }
  }
}
```

Supports both stdio servers (`command` + `args`) and SSE servers (`type: "sse"` + `url`).

## How do I run on a GPU server or HPC cluster?

See [Remote Sandboxes](remote-sandboxes.md). Short version:

1. Pull the sandbox image on the remote machine
2. Add the remote sandbox in **Settings → Remote Sandboxes**
3. Select it when starting a run

## How do I set a budget or time limit?

**Budget:** In the New Run modal, expand **Budget**, enable the cap, and set a dollar amount. The agent stops when it hits the limit.

**Time limit (Session Duration):** Pick a duration preset (30 min, 1 hour, etc.) in the New Run modal. The agent is denied from ending the session early — it must work for the full duration before it can create a PR and stop.

"No lock" (default) lets the agent end whenever it thinks it's done.

## What model should I use?

- **Claude Opus 4.6** — most capable, best for complex multi-file tasks. Default.
- **Claude Sonnet 4.6** — faster and cheaper, good for straightforward tasks.
- **Claude Opus 4.5** — legacy, available for comparison.

Change the model in the **Model** section of the New Run modal.

**Thinking Effort** controls how much the model reasons before acting: `low`, `medium`, `high` (default), `max`. Higher effort = better results but more tokens.

## What do the starter presets do?

| Preset | What it does |
|--------|-------------|
| **Security hardening** | Audits the codebase for vulnerabilities (OWASP top 10, injection, auth issues) and fixes them |
| **Bug bash** | Searches for bugs through code review, edge cases, and error handling gaps |
| **Code quality** | Refactors for performance, readability, and maintainability |
| **Test coverage** | Identifies untested code paths and adds tests |

Each preset expands to a detailed markdown prompt. You can also write your own goal in the Custom Prompt field.

## The agent keeps ending early. How do I make it work longer?

Set a **Session Duration** when starting the run. With a duration set, the agent's `end_session` tool is denied until the timer expires. It's forced to keep iterating.

Without a duration ("No lock"), the agent decides when it's done — which may be too soon for complex tasks.

## The agent is stuck or going in circles. What do I do?

**Inject a prompt.** Click the chat input at the bottom of the run feed and send a message. The agent receives it as a user turn in its next context window and can course-correct.

Examples:
- "You're overcomplicating this. Just use the existing auth middleware."
- "The test is failing because you need to run migrations first."
- "Focus on the API layer, skip the frontend for now."

## How do I switch repos?

AutoFyn auto-detects the repo from your local git remote. To change it:

**Dashboard:** The repo selector is in the sidebar header. Click it to switch between configured repos.

**CLI:**
```bash
autofyn repos list
autofyn repos set-active owner/other-repo
```

## How do I use multiple Claude API keys?

AutoFyn uses a **token pool**. Add multiple tokens and it rotates through them to avoid rate limits:

```bash
autofyn settings set --claude-token sk-ant-first-key
autofyn settings set --claude-token sk-ant-second-key
```

Or add them in the dashboard under **Settings → API Tokens**.

## How do I give the agent Docker access?

```bash
autofyn start --allow-docker
```

This mounts the host Docker socket into sandbox containers. The agent can then build images, run containers, etc. Only use this if your task specifically requires Docker — it gives the agent full control over the host Docker daemon.

## Where are the logs?

```bash
autofyn logs              # Stream all container logs
autofyn logs 50           # Last 50 lines + follow
```

Connector logs: `~/.autofyn/.connector.log`

Individual container logs are also available via `docker compose logs <service>` from `~/.autofyn`.
