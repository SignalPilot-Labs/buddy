# SignalPilot Feature Table
**Date:** March 30, 2026
**Sources:** signalpilot-sandbox-spec.md + sp-e2b-reality.md
**Ranked by:** importance to shipping a working, trusted product

---

| # | Feature | Pillar | Who Builds It | E2B Role | MVP? | Notes |
|---|---------|--------|---------------|----------|------|-------|
| 1 | **SQL read-only enforcement** — AST parse every query, block DDL/DML and statement stacking at the gateway | Ship Faster | Us (sqlglot) | None | ✅ Week 1 | This is the CVE that killed Anthropic's Postgres MCP. Non-negotiable day one. |
| 2 | **Credential vault** — encrypted storage of DB connection strings; never exposed to agents, LLMs, or sandbox | Ship Faster | Us | None | ✅ Week 1 | Gateway holds credentials. Sandbox gets a session token, not the raw string. |
| 3 | **Session-token isolation** — sandbox receives `SP_SESSION_TOKEN` + `SP_GATEWAY_URL` only; all DB calls route through the gateway | Ship Faster | Us | E2B injects env vars | ✅ Week 3 | `egressTransform` not shipped; this is the correct alternative. |
| 4 | **PostgreSQL connector** — asyncpg-backed, implements the full connector interface (connect, execute, estimate cost, get schema, health check, close) | Ship Faster | Us | None | ✅ Week 1 | P0. Every dev has one. Covers RDS, Supabase, Neon. |
| 5 | **MCP server + tool registration** — `connect_database`, `query_database`, `list_tables`, `describe_table`, `run_analysis`, `check_budget` exposed as MCP tools | Ship Faster | Us (claude_agent_sdk + official MCP SDK) | None | ✅ Week 1 | Works with Claude Code, Cursor, any MCP client out of the box. |
| 6 | **Audit log** — append-only JSONL: question → SQL → tables → columns → rows → cost → PII redacted → approval reason → agent identity | Analyze Better | Us entirely | None | ✅ Week 1 | Nothing from E2B. We write every event. |
| 7 | **Row limit injection** — inject or override LIMIT clause on all queries at the gateway before execution | Analyze Better | Us | None | ✅ Week 1 | Prevents context window overflow and runaway scans. |
| 8 | **Query timeout enforcement** — per-query hard timeout; cancel on the DB side (not just client-side) | Ship Faster | Us | `run_code(timeout=N)` for sandbox path | ✅ Week 1 | E2B's timeout param handles the sandbox side. Gateway handles the direct DB side. |
| 9 | **DuckDB connector** — zero-config local analytics, covers MotherDuck cloud | Ship Faster | Us | None | ✅ Week 4 | P0 for demos and local dev. Ships week 4. |
| 10 | **Sandboxed Python execution** — `run_analysis` tool spins up an E2B microVM, runs arbitrary Python with pandas/matplotlib/scipy, sandbox queries DB only through the gateway | Analyze Better | Us (tool) + E2B (compute) | Firecracker microVM, ~150ms cold start, persistent state across calls | ✅ Week 3 | E2B's core contribution. We own the governance wrapper around it. |
| 11 | **Per-session budget ledger** — hard USD spending limit per agent/session; gateway hard-stops when reached | Spend Less | Us entirely | None | ✅ Week 3 | No E2B billing API. We track `startedAt`/`endAt` + pricing formula ourselves. |
| 12 | **Compute cost tracking** — sandbox wall-clock time × vCPU rate + memory rate, added to session budget ledger | Spend Less | Us (formula) | `get_info()` timestamps | ✅ Week 3 | Formula: `duration_sec × cpu_count × $0.000014 + duration_sec × memory_gib × $0.0000045` |
| 13 | **DB query cost pre-estimation** — EXPLAIN/dry-run before execution, block or warn if over budget threshold | Spend Less | Us | None | ✅ Week 3 | Postgres: EXPLAIN row estimates. Snowflake: bytes scanned. BigQuery: dry-run. |
| 14 | **PII column tagging** — schema.yml flags columns as PII with redaction rule (hash, mask, drop) | Analyze Better | Us | None | ✅ Week 3 | Loaded from annotations, applied at result governance step. |
| 15 | **PII redaction in results** — before returning query results to agent, hash/mask/drop flagged columns | Analyze Better | Us | None | ✅ Week 3 | Applied post-execution, pre-return. Agent never sees raw PII. |
| 16 | **Schema annotations** — YAML sidecar file with table descriptions, column business definitions, owners, sensitivity levels, blocked tables | Analyze Better | Us (format + loader) | None | ✅ Week 3 | Lives alongside dbt models or in `~/.signalpilot/`. |
| 17 | **CLI: `sp connect`** — one command to connect a database and expose a governed MCP endpoint | Ship Faster | Us | None | ✅ Week 1-2 | The demo moment. Target: working endpoint in under 60 seconds. |
| 18 | **Schema caching** — on session open, introspect and cache full schema so `list_tables`/`describe_table` are instant | Analyze Better | Us | None | ✅ Week 1 | Avoids repeated schema queries. Refreshable on demand. |
| 19 | **Blocked tables enforcement** — tables listed in `blocked_tables` in schema.yml are rejected at the policy check step, before execution | Analyze Better | Us | None | ✅ Week 1 | Policy check happens after SQL parse, before cost estimation. |
| 20 | **Snowflake connector** — with bytes-scanned cost estimation model | Spend Less | Us | None | ✅ Week 4 | P1. Highest cost-blowup risk of any database. |
| 21 | **Sandbox outbound network lockdown** — sandbox can only reach our gateway; all other outbound traffic denied | Ship Faster | Us (config) + E2B (enforcement) | `network: { allowOut: [gateway_url], denyOut: ["0.0.0.0/0"] }` | ✅ Week 3 | E2B's allow/deny lists are shipping. HTTP+HTTPS only. UDP not filtered. |
| 22 | **Real-time sandbox metrics** — CPU%, memory, disk usage polled every 5 seconds via `get_metrics()` | Spend Less | E2B (collection) + Us (ledger) | `sandbox.get_metrics()` | ✅ Week 3 | First metrics available ~5s after creation. Used for utilization-based cost accounting. |
| 23 | **Connector registry** — standardized interface (connect, execute, estimate_cost, get_schema, health_check, close) all connectors implement | Ship Faster | Us | None | ✅ Week 1 | Makes adding new databases a one-connector job. |
| 24 | **Custom E2B template (`signalpilot-base`)** — pre-installed: asyncpg, snowflake-connector, duckdb, pandas, numpy, matplotlib, sqlglot + our `sandbox_agent` process | Ship Faster | Us (Dockerfile) + E2B (build + snapshot) | Builds template, snapshots VM, ~150ms cold start on create | ✅ Week 3 | Snapshot restore is why cold start is fast. Template locked to Debian-based images only. |
| 25 | **`sandbox_agent` in-VM process** — lightweight process that starts with the VM, reads session token, proxies all DB calls to our gateway, enforces local timeout | Ship Faster | Us entirely | Runs inside E2B VM | ✅ Week 3 | The enforcement layer inside the sandbox. No direct DB access possible. |
| 26 | **Result-set sampling** — intelligent TABLESAMPLE or LIMIT injection for large tables | Analyze Better | Us | None | ✅ Week 1 | Part of row limit injection. Prevents LLM context overflow. |
| 27 | **Filesystem event watching** — `watch_dir()` for observing file changes inside sandbox | Analyze Better | E2B | `sandbox.files.watch_dir()` | Deferred | Useful for tracking output files (charts, CSVs). Minor edge cases with rapidly created nested folders. |
| 28 | **Multi-source queries** — route queries to different connectors, merge results in sandbox via pandas | Analyze Better | Us (routing) + E2B (sandbox memory) | Sandbox holds DataFrames in memory | Deferred Month 2 | Connector registry routes by connection name. Merge in sandbox Python. |
| 29 | **Schema introspection CLI (`sp init`)** — generate starter `schema.yml` from DB introspection | Analyze Better | Us | None | ✅ Week 4 | Lowers annotation friction. DB → YAML skeleton, human fills in descriptions. |
| 30 | **Query deduplication + caching** — SHA-256 of normalized SQL → cached result with TTL | Spend Less | Us | Sandbox filesystem (optional) | Deferred Month 2 | Same query within N minutes returns cached data. Saves cost on repeat questions. |
| 31 | **Connection health monitoring** — per-connection latency, error rate, pool utilization, alerting | Spend Less | Us | None | Deferred Month 2 | P99 latency tracking. Alert when a warehouse degrades before it cascades. |
| 32 | **MySQL connector** | Ship Faster | Us | None | Deferred Month 2 | P1. Covers PlanetScale, TiDB, Aurora MySQL. |
| 33 | **BigQuery connector** — with dry-run cost estimation | Spend Less | Us | None | Deferred Month 2 | Dry-run gives exact bytes before execution. Best cost estimation of any connector. |
| 34 | **Sandbox pause/resume** — pause idle sandboxes to stop billing, resume on next message | Spend Less | E2B (beta) + Us (orchestration) | `sandbox.pause()` / `sandbox.connect()` | Deferred Month 2 | ~4s per GiB RAM to pause. Known persistence bug across multiple cycles. Treat as beta. |
| 35 | **Usage dashboard** — queries executed, budget consumed, top tables accessed, recent audit entries | Analyze Better | Us | None | ✅ Week 4 | Terminal-based for MVP. Web UI deferred. |
| 36 | **Databricks connector** — Unity Catalog integration | Ship Faster | Us | None | Deferred Month 2-3 | P2. Growing enterprise presence. |
| 37 | **Redshift connector** — via Postgres wire protocol | Ship Faster | Us | None | Deferred Month 2-3 | P3. AWS analytics warehouse. |
| 38 | **Rich sandbox output** — charts (.png), DataFrames (.html), JSON returned from `run_analysis` | Analyze Better | E2B (`execution.results`) | `run_code()` returns `.png`, `.html`, `.json` | ✅ Week 3 | Only via `e2b_code_interpreter` package, not base `e2b` SDK. |
| 39 | **Human-in-the-loop approval queue** — flag expensive or sensitive queries for human review before execution | Ship Faster | Us | None | Deferred Month 2 | Requires UI. Auto-approve by policy is enough for MVP. |
| 40 | **PyPI packaging** (`uvx signalpilot`) | Ship Faster | Us | None | ✅ Week 4 | Published to PyPI, invoked via `uvx` (zero-install) or Docker. `claude mcp add signalpilot -- uvx signalpilot serve prod-analytics`. |
| 41 | **Sandbox-per-session model** — one E2B sandbox per conversation session, killed at end | Ship Faster | Us (orchestration) + E2B (isolation) | One Firecracker VM per session | ✅ Week 3 | Simpler billing, stronger isolation than sandbox-per-agent. Default 1hr timeout. |
| 42 | **Multi-tenant cloud service** — SignalPilot as a hosted SaaS | Ship Faster | Us | None | Deferred Month 3-6 | MVP is single-tenant CLI. Cloud is the scale play. |
| 43 | **`signalpilot-heavy` template** — 4 vCPU / 4 GiB for Pro customers doing intensive analysis | Analyze Better | Us (Dockerfile) + E2B (build) | CPU/RAM set at template build time only — cannot change at `Sandbox.create()` | Deferred Month 2 | E2B Pro plan required for CPU/RAM customization. |
| 44 | **SSO / SAML** | Ship Faster | Us | None | Deferred Month 3 | Enterprise feature. API key auth is fine for MVP. |
| 45 | **Compliance report exports** (SOC 2, HIPAA, EU AI Act) | Analyze Better | Us | None | Deferred Month 3-4 | Audit log exists from day one. Formatted exports come later. |
| 46 | **Schema intelligence / ML-powered suggestions** — AI-suggested annotations, query recommendations | Analyze Better | Us | None | Deferred Month 6+ | Annotations first. ML layer later. |
| 47 | **Shadow AI detection** — detect agents querying without going through SignalPilot | Ship Faster | Us | None | Deferred Month 6+ | Requires network-level visibility. Enterprise feature. |
| 48 | **On-prem / BYOC deployment** — self-hosted Firecracker fleet | Ship Faster | Us (Phase 2) | E2B only for burst | Deferred Month 6+ | Phase 2 migration gives us full control: cgroup limits, network interception, billing granularity. |
| 49 | **GPU support** | Analyze Better | N/A | Not possible | Never (E2B) | Architectural impossibility — Firecracker has no PCIe support. Phase 2 self-hosted would need QEMU or another hypervisor. |

---

## Key Constraints to Keep Visible

| Constraint | Impact |
|-----------|--------|
| E2B CPU/RAM only configurable at template build time | Different resource tiers = different pre-built templates. Cannot resize a running sandbox. |
| No E2B billing API | We derive cost from `startedAt`/`endAt` timestamps + pricing formula. We own the ledger. |
| `egressTransform` not shipped | Credential isolation = session-token → gateway approach. Raw creds never enter the sandbox. |
| No per-execution resource limits in E2B | Timeout (`run_code(timeout=N)`) and row limits are our primary levers. |
| Debian-based images only | No Alpine, CentOS, Fedora, Arch base images in E2B templates. |
| Template size cap ~4.3 GiB | Keep pre-installed packages lean; install heavy deps at runtime or split templates. |
| `run_code()` only on `e2b_code_interpreter.Sandbox` | Don't mix with base `e2b.Sandbox` — they are different classes with different APIs. |
| Sandbox pause is beta | ~4s/GiB pause time, known persistence bug across multiple cycles. Don't rely on it for critical state. |
| E2B metrics lag ~5s | First `get_metrics()` call after create returns empty. Build in a small wait or handle gracefully. |
| Sandbox concurrency: 100 (Pro) | Fine for MVP. At scale, negotiate higher limits or migrate to self-hosted. |
