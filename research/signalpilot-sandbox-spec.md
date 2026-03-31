# SignalPilot Sandbox: Broad MVP Spec
**Date:** March 30, 2026
**Status:** Draft
**Backend:** E2B Cloud (Phase 1) → Self-hosted Firecracker (Phase 2+)

> Build the secure database sandbox as a cloud service on E2B's infrastructure now, while engineering our own isolation layer in parallel. Ship in weeks, not quarters.

---

## How SignalPilot Connects: The Core Tool Definition

This is the beating heart of the product. SignalPilot exposes a single primary tool to any AI agent — `connect_database` — that wires the agent into a governed, sandboxed database session in one call. Everything else (query execution, schema exploration, cost tracking, audit logging) flows from this connection.

### The Tool

**Name:** `connect_database`

**Description:**
> "Connect to a database and open a governed session. Once connected, you can query the database with read-only SQL, explore the schema, run Python analysis in a secure sandbox, and check your query budget. All queries are intercepted, validated against policies, cost-estimated, and logged before reaching the database. PII columns are automatically redacted. State persists across calls within this session — query results, installed packages, and sandbox variables all survive between tool invocations. The session is automatically torn down when you disconnect."

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "connection_name": {
      "type": "string",
      "description": "The name of a pre-registered connection (e.g. 'prod-analytics', 'snowflake-dw'). Must exist in the SignalPilot credential vault."
    },
    "session_config": {
      "type": "object",
      "description": "Optional per-session overrides for governance defaults.",
      "properties": {
        "row_limit": {
          "type": "integer",
          "description": "Maximum rows returned per query. Overrides connection default. Hard ceiling: 100,000.",
          "default": 10000
        },
        "budget_usd": {
          "type": "number",
          "description": "Maximum USD to spend on database queries this session. Gateway hard-stops when reached.",
          "default": 10.0
        },
        "timeout_seconds": {
          "type": "integer",
          "description": "Per-query execution timeout. Query is cancelled on the database side (not just client-side) when exceeded.",
          "default": 30
        },
        "sandbox_enabled": {
          "type": "boolean",
          "description": "Whether to spin up an E2B sandbox for Python analysis. If false, only SQL queries are available.",
          "default": true
        }
      }
    }
  },
  "required": ["connection_name"]
}
```

**Returns:** Standard MCP content block:
```json
{
  "content": [
    {
      "type": "text",
      "text": "Connected to prod-analytics (PostgreSQL 15.4). 47 tables available. Sandbox ready. Budget: $10.00 remaining. Session ID: sess_01HX9K..."
    }
  ]
}
```

On failure (bad credentials, connection refused, budget already exhausted):
```json
{
  "content": [
    {
      "type": "text",
      "text": "Error: Connection 'prod-analytics' failed — could not reach host at db.company.com:5432. Check that the host is reachable and credentials are valid."
    }
  ],
  "isError": true
}
```

---

### How It's Built

The `@tool` decorator from `claude_agent_sdk` registers it as an MCP-compatible tool. The tool closes over the session state object — so the same governed session (sandbox, budget ledger, audit context, DB connection pool) persists across every tool call within a conversation:

```python
@tool(
    "connect_database",
    """Connect to a database and open a governed session. Once connected, you can query
    with read-only SQL, explore the schema, run Python analysis in a secure sandbox,
    and check your query budget. All queries are intercepted, validated, cost-estimated,
    and logged. PII columns are automatically redacted. State persists across calls.""",
    {
        "connection_name": str,
        "session_config": dict  # optional
    }
)
async def connect_database(args: dict) -> dict:
    config = args.get("session_config", {})

    # 1. Load credentials from vault (never exposed to agent)
    creds = await credential_vault.get(args["connection_name"])

    # 2. Open DB connection pool through connector registry
    connector = ConnectorRegistry.get(creds.db_type)
    await connector.connect(creds, config)

    # 3. Spin up E2B sandbox (if enabled), injecting session token not raw creds
    sandbox = None
    if config.get("sandbox_enabled", True):
        sandbox = await Sandbox.create(template="signalpilot-base")
        await sandbox.env.set("SP_SESSION_TOKEN", session.token)
        await sandbox.env.set("SP_GATEWAY_URL", GATEWAY_URL)
        # Raw DB credentials are NEVER injected into sandbox env

    # 4. Initialize governance context for this session
    session = GovernanceSession(
        connection_name=args["connection_name"],
        connector=connector,
        sandbox=sandbox,
        budget_usd=config.get("budget_usd", 10.0),
        row_limit=config.get("row_limit", 10000),
        timeout_seconds=config.get("timeout_seconds", 30),
        audit_log=AuditLog.new_session(),
    )

    # 5. Cache schema so downstream tools can introspect without extra queries
    schema = await connector.get_schema()

    return {
        "content": [{
            "type": "text",
            "text": session.connection_summary(schema)
            # e.g. "Connected to prod-analytics (PostgreSQL 15.4). 47 tables available.
            #        Sandbox ready. Budget: $10.00 remaining. Session: sess_01HX9K..."
        }]
    }
```

Then `create_sdk_mcp_server` wraps it into an in-memory MCP server object:

```python
signalpilot_server = create_sdk_mcp_server(
    "signalpilot",
    tools=[
        connect_database,   # opens the governed session
        query_database,     # runs validated SQL through the governance pipeline
        list_tables,        # schema exploration from cached schema
        describe_table,     # column-level detail + sample values
        run_analysis,       # executes Python in the E2B sandbox
        check_budget,       # returns remaining budget + spend so far
    ]
)
```

---

### How It Connects to the Agent

The server is passed directly to `ClaudeAgentOptions` as a named MCP server:

```python
options = ClaudeAgentOptions(
    mcp_servers={"signalpilot": signalpilot_server},
    permission_mode="bypassPermissions",
    system_prompt="""You have access to a governed database session via SignalPilot.
    Always call connect_database first. All your SQL queries will be validated,
    cost-estimated, and logged. PII columns are automatically redacted.
    You have a sandbox available for Python analysis."""
)
```

There is no network transport — no stdio, no HTTP, no sidecar process. The MCP server lives in-process. `ClaudeSDKClient` wires it directly into Claude's agent loop, so Claude sees all six SignalPilot tools as natively available and can call them in sequence within a single conversation turn.

---

### Key Architecture Points

**Session closure over state.** The `GovernanceSession` object is created inside `connect_database` and closed over by all other tools (`query_database`, `run_analysis`, etc.). Every subsequent tool call in the session shares the same connector, sandbox, budget ledger, and audit log — exactly like the E2B sandbox pattern where the same sandbox instance persists across every `run_python` call.

**Sandbox never gets raw credentials.** The E2B sandbox receives only a short-lived session token pointing at the SignalPilot gateway. When the sandbox wants to query a database, it calls the gateway (which validates, logs, and enforces budgets) — not the database directly. Raw connection strings never enter the sandbox environment.

**Governance is not optional.** There is no code path from the agent to the database that bypasses the query engine. The connector object lives only inside the `GovernanceSession`. The sandbox has no access to the connector — only to the gateway's governed HTTP endpoint. This is the architectural guarantee, not just a policy.

**Teardown is automatic.** At the end of the agent loop (or on session timeout), `session.close()` calls `sandbox.kill()`, closes the DB connection pool, flushes the audit log, and zeroes the session budget. No resources leak between conversations.

---

## Guiding Principle: E2B Is the Engine, We're the Dashboard + Governance

E2B gives us Firecracker microVMs with sub-200ms cold starts, persistent filesystem, and any-language execution. We don't need to build compute isolation from scratch. What E2B **doesn't** give us -- and what nobody gives anyone -- is:

- SQL-aware query interception
- Per-agent cost controls
- Schema-aware governance
- Compliance-grade audit trails
- Database connector management

That's the product. E2B is the runtime. We are the brain.

---

## Architecture: Phase 1 (E2B Backend)

**AI Clients** (Claude Code, Cursor, GPT, custom agents, any MCP client) connect via the MCP protocol to the **SignalPilot Gateway Service**, which contains three core subsystems:

- **MCP Server** — tool registration, auth/key management, rate limiting, routing
- **Query Engine** — SQL parsing, AST analysis, cost estimation, read-only enforcement, DDL/DML gating, row limits
- **Governance Layer** — agent identity, per-agent budgets, schema policies, audit logging, PII tagging, approval queues

The Gateway connects out to a **Connector Registry** for each supported database, and can route execution through two paths:

1. **Direct DB query** (fast path) — SQL goes straight to the database, governed by the query engine. Sub-second. No sandbox needed.
2. **Sandboxed code execution** (E2B path) — Python/analysis code runs inside an E2B microVM. The sandbox queries databases only through the governed gateway path.

---

## The Three Pillars

### SHIP FASTER
> "AI features that used to be blocked now launch."

- **One-command connect** — a single CLI command connects any supported database and exposes a governed MCP endpoint in under a minute
- **Protocol-level read-only enforcement** — SQL is intercepted and validated at the gateway before it ever reaches the database; blocks statement stacking, DDL, and DML
- **Pre-built database connectors** — standardized connectors for all major databases so teams don't spend weeks building integrations
- **Credential vault** — encrypted credential storage; credentials are never exposed to agents or LLMs
- **MCP-native from day one** — gateway exposes tools as MCP resources; works with any MCP client out of the box

### ANALYZE BETTER
> "AI answers get more accurate and trustworthy."

- **Schema annotations** — human-authored descriptions, business glossary, sensitivity levels, and ownership attached to tables and columns so AI understands context
- **Full-chain audit log** — every query is traceable from the original natural-language question through the generated SQL, the tables and columns accessed, rows returned, cost, and approval decision
- **Result-set sampling** — gateway-level row limits and intelligent sampling prevent context window overflow and reduce LLM token cost
- **Sandboxed Python analysis** — data scientists get a real execution environment (pandas, matplotlib, etc.) with governed database access
- **Multi-source queries** — the connector registry routes queries to the right database; results can be merged across sources in the sandbox

### SPEND LESS
> "AI that pays for itself instead of surprising you with bills."

- **Query cost pre-estimation** — cost is estimated before execution using database-native explain/dry-run mechanisms; expensive queries are blocked or require approval
- **Per-agent budgets** — hard spending limits per agent; the gateway stops execution when the budget is hit
- **E2B cost passthrough** — sandbox compute time is tracked per agent and included in the budget ledger
- **Query deduplication and caching** — identical queries within a time window return cached results instead of hitting the database again
- **Connection health monitoring** — per-connection latency, error rates, and pool utilization are tracked with alerting on degradation

---

## Query Engine: The SQL Gatekeeper

Every query passes through a multi-stage pipeline before reaching the database:

1. **SQL Parse** — parse to AST, extract tables/columns/operations, detect statement stacking
2. **Policy Check** — verify tables are allowed, check column-level access, enforce read-only
3. **Cost Estimation** — run a dry-run or explain against the database, compare to budget, block if over limit
4. **Row Limit Injection** — inject or enforce a maximum row limit on all queries
5. **Execute + Timeout** — execute with a hard timeout; cancel on the database side, not just the client
6. **Result Governance** — redact PII columns (hash/mask/drop), truncate oversized results, format for LLM consumption
7. **Audit Log** — append a structured record of the full chain to the audit log

---

## Database Connectors

Connectors are built in priority order based on market coverage:

| Priority | Database | Rationale |
|----------|----------|-----------|
| P0 | PostgreSQL | Most common starting point; covers AWS RDS, Supabase, Neon, etc. |
| P0 | DuckDB | Zero-config local analytics; great for demos and MotherDuck cloud |
| P1 | Snowflake | Highest cost-blowup risk; largest enterprise data warehouse |
| P1 | MySQL | Second most common RDBMS; covers PlanetScale, TiDB, Aurora MySQL |
| P2 | BigQuery | Google Cloud analytics |
| P2 | Databricks | Unity Catalog; growing enterprise presence |
| P3 | Redshift | AWS analytics; partial Postgres wire protocol compatibility |

Every connector implements a standardized interface: connect, execute, estimate cost, get schema, health check, close.

---

## Schema Annotations

A YAML sidecar file (living in the repo alongside dbt models or in a config directory) lets teams attach human knowledge to the database schema:

- Table descriptions, owners, and sensitivity levels
- Column descriptions, units, and business definitions
- PII flags with redaction rules (hash, mask, or drop)
- Blocked tables that AI agents should never query

This is how AI goes from guessing which of six revenue tables is correct to knowing exactly which one the finance team uses for board reporting.

---

## Audit Log

Every query produces a structured log entry capturing:

- Timestamp and event ID
- Connection name
- Agent identity (type, model, session)
- User identity
- Original natural-language request
- Generated SQL
- Tables and columns accessed, including PII columns
- Rows scanned and rows returned
- Execution time and cost
- Governance decision (policy applied, approval reason, budget remaining, PII redaction applied)

---

## MCP Tools Exposed (MVP)

- **query_database** — execute a read-only SQL query; all queries are validated, cost-estimated, and logged
- **list_tables** — list all tables the agent has access to, with descriptions and row count estimates
- **describe_table** — get column names, types, descriptions, and sample values for a table
- **run_analysis** — execute Python code in a secure sandbox with governed database access
- **check_budget** — check remaining query budget for the current agent/session

---

## E2B Integration

### What E2B Handles
- Compute isolation via Firecracker microVMs
- Persistent state across tool calls
- Pre-installed analysis packages
- Sandbox timeout enforcement

### What We Handle
- Governed database access from inside the sandbox (all sandbox queries route through the gateway, never direct)
- Custom sandbox template with pre-installed database connectors
- Per-session cost tracking and budget inclusion

### Sandbox Model (MVP)
One sandbox per user session with a default 1-hour timeout. Simple billing, strong isolation.

---

## Phase 1 → Phase 2: Building Our Own Runtime

### Why E2B First
- Fastest time to market — days of integration, not months of infrastructure
- Proven security isolation (same Firecracker technology as AWS Lambda)
- Cheaper than running our own fleet until meaningful scale
- Lets us focus engineering on governance, which is the actual product

### Why We Eventually Migrate
- Margin: E2B takes a significant cut of compute cost at scale
- Latency: removing the network hop to E2B API
- Compliance: some customers require on-prem or single-tenant deployments
- Customization: microVM images optimized for database workloads

### Migration Phases
- **Phase 1 (Months 1-3):** E2B Cloud — ship fast, validate PMF, zero infra ops
- **Phase 2 (Months 4-8):** Hybrid — Firecracker on our own infrastructure, E2B as burst fallback
- **Phase 3 (Month 9+):** Self-hosted — full Firecracker fleet, E2B only for BYOC enterprise customers

---

## MVP Scope: What Ships in 4 Weeks

### Week 1-2: Core Gateway + Postgres Connector
- Core connector interface + PostgreSQL implementation
- SQL parser with read-only enforcement and statement stacking detection
- Row limit injection and query timeout enforcement
- Audit logging
- MCP server with query, list tables, and describe table tools
- CLI for connecting a database and serving an MCP endpoint

### Week 3: E2B Sandbox + Governance
- E2B sandbox integration with run_analysis tool
- Custom sandbox template
- Governed sandbox database access (no raw credentials in sandbox)
- Per-agent budget tracking
- Cost estimation for Postgres
- PII column tagging and redaction from schema annotations

### Week 4: Polish + Ship
- DuckDB connector
- Snowflake connector with cost estimation
- Schema introspection to generate starter annotations
- Basic usage dashboard (queries, budget, top tables, recent audit entries)
- Documentation and quickstart guide
- PyPI packaging

---

## What's NOT in MVP

| Feature | When |
|---------|------|
| MySQL, BigQuery, Databricks, Redshift connectors | Month 2-3 |
| Human-in-the-loop query approval workflows | Month 2 |
| SSO / SAML | Month 3 |
| Compliance report exports (SOC 2, HIPAA, EU AI Act) | Month 3-4 |
| Web dashboard | Month 2-3 |
| Multi-tenant cloud service | Month 3-6 |
| Schema intelligence / ML-powered suggestions | Month 6+ |
| Shadow AI detection | Month 6+ |
| On-prem / BYOC deployment | Month 6+ |

---

## Tech Stack (MVP)

| Layer | Choice |
|-------|--------|
| Language | Python 3.12+ |
| MCP SDK | Official Python MCP SDK |
| SQL Parser | sqlglot (all dialects, AST-level, MIT license) |
| DB Drivers | Best-in-class async driver per database |
| Sandbox | E2B code interpreter SDK |
| Audit Store | JSONL files (MVP) → SQLite → Postgres (cloud) |
| Budget Store | SQLite (local) → Postgres (cloud) |
| Config | YAML (schema.yml, config.yml) |
| CLI | Standard Python CLI framework (click/typer) |
| Distribution | PyPI via `uvx signalpilot` (zero-install) + Docker |

---

## Pricing Model (Launch)

| Tier | Price | Target |
|------|-------|--------|
| Free | $0 | Solo dev evaluating |
| Pro | $99/mo | Startup data team |
| Enterprise | Custom | Regulated industries |

---

## Success Metrics (First 90 Days)

| Metric | Target |
|--------|--------|
| PyPI installs | 1,000 |
| Successful `sp connect` completions | 500 |
| GitHub stars | 200 |
| Queries governed (opt-in telemetry) | 100K |
| Paying Pro customers | 10 |
| Enterprise design partners | 3 |
| Security incidents through SignalPilot | 0 |

---

## The Compound Bet

- **Week 1:** Developer connects Postgres → 30 seconds to a governed MCP endpoint → **Ship Faster**
- **Week 2:** Adds schema annotations → AI queries the right table → **Analyze Better**
- **Week 3:** Connects Snowflake, sets daily budget → no surprise bills → **Spend Less**
- **Month 2:** Adds team member, needs audit trail → full-chain logging already exists → **Analyze Better**
- **Month 3:** Compliance review → audit export passes → **Ship Faster**
- **Month 6:** Can't leave — audit history, schema annotations, budget data, and compliance records are organizational IP that doesn't transfer to a competitor → **Moat**

E2B proved that sandboxing AI execution is a $32M+ market. SignalPilot takes that model and goes deeper on the one thing E2B explicitly doesn't do: **govern what AI agents do with your data.**

---

*This spec builds on: secure-sandbox-wedge.md (the bet), spec-enablement.md (the feature-to-outcome map), sp-ai-resistance-play.md (the defensibility thesis), sp-market-research.md (demand validation), market-research-mcp-gateway-2026.md (competitive landscape), and e2b-local/ (sandbox prototyping).*
