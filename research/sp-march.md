# SignalPilot: Next 72 Hours
**Date:** March 30, 2026
**Goal:** Buildable systems design for four workstreams — ship the skeleton, prove it works, measure it against the best public benchmark.

---

## Workstream Overview

```
 Day 1 (Mon)                    Day 2 (Tue)                     Day 3 (Wed)
 ───────────                    ───────────                     ───────────
 Project scaffold               UI shell + dashboard            Spider 2.0 harness
 Postgres connector             MCP server wired to UI          First benchmark run
 SQL parser (read-only)         Docker image builds             Improvement loop v1
 Audit log writes               `sp connect` CLI works          Publish results
```

---

## 1. Delivery Mode: How SignalPilot Gets to Users

Three delivery surfaces, one gateway core.

```mermaid
flowchart TB
    subgraph USER_INSTALL["User Runs SignalPilot"]
        UVX["uvx signalpilot"]
        DOCKER["docker run signalpilot"]
    end

    subgraph CLI_PATH["MCP Server Path (Primary — Day 1)"]
        SP_CONNECT["sp connect postgres://..."]
        SP_SERVE["sp serve prod-analytics"]
    end

    subgraph DOCKER_PATH["Docker Path (Day 2)"]
        COMPOSE["docker-compose.yml"]
        GW_CONTAINER["signalpilot-gateway container"]
        UI_CONTAINER["signalpilot-ui container"]
    end

    subgraph GATEWAY["SignalPilot Gateway (Python Process)"]
        MCP_SERVER["MCP Server\n(stdio or SSE)"]
        QUERY_ENGINE["Query Engine\n(sqlglot AST)"]
        GOVERNANCE["Governance\n(budget, PII, audit)"]
        CONNECTORS["Connector Registry"]
    end

    subgraph AI_CLIENTS["AI Clients"]
        CLAUDE["Claude Code"]
        CURSOR["Cursor"]
        CUSTOM["Custom Agents"]
    end

    subgraph DATABASES["Databases"]
        PG["PostgreSQL"]
        DUCK["DuckDB"]
        SNOW["Snowflake"]
    end

    UVX --> SP_CONNECT
    SP_CONNECT --> SP_SERVE
    SP_SERVE --> MCP_SERVER

    DOCKER --> COMPOSE
    COMPOSE --> GW_CONTAINER
    COMPOSE --> UI_CONTAINER
    GW_CONTAINER --> MCP_SERVER
    UI_CONTAINER -->|"REST API\nport 3100"| GW_CONTAINER

    AI_CLIENTS -->|"MCP protocol\nstdio / SSE"| MCP_SERVER
    MCP_SERVER --> QUERY_ENGINE
    QUERY_ENGINE --> GOVERNANCE
    GOVERNANCE --> CONNECTORS
    CONNECTORS --> DATABASES
```

### Delivery Priority

| Surface | Day | What Ships | How |
|---------|-----|-----------|-----|
| **MCP Server** (`uvx signalpilot serve`) | Day 1 | `sp connect` + `sp serve` — working MCP endpoint over stdio | `uvx` runs directly from PyPI, zero install. Also: `claude mcp add signalpilot -- uvx signalpilot serve prod-analytics` |
| **Docker** | Day 2 | `docker-compose up` — gateway + UI in two containers | Dockerfile + compose.yml, gateway exposes SSE on port 3100 |
| **UI** | Day 2-3 | Next.js dashboard at `localhost:3000`, talks to gateway REST API | Separate container, optional — MCP server works without it |

### MCP Transport Decision

```mermaid
flowchart LR
    STDIO["stdio transport\n(pipe to Claude Code / Cursor)"]
    SSE["SSE transport\n(HTTP, for UI + remote agents)"]
    GATEWAY["Gateway Process"]

    GATEWAY -->|"sp serve --stdio"| STDIO
    GATEWAY -->|"sp serve --sse --port 3100"| SSE

    STDIO -->|"Local dev\nClaude Code adds:\nclaude mcp add signalpilot --\nuvx signalpilot serve prod-analytics"| LOCAL["Local AI Client"]

    SSE -->|"Docker / remote\nUI dashboard\nRemote agents"| REMOTE["UI + Remote Clients"]
```

**Day 1:** stdio only (simplest, works immediately with Claude Code).
**Day 2:** Add SSE endpoint so the UI container and remote agents can connect.

---

## 2. UI: Next.js/React Frontend

The UI is a monitoring and management dashboard, not a query interface. The AI client (Claude Code, Cursor) is where queries happen. The UI shows what's happening.

```mermaid
flowchart TB
    subgraph NEXTJS_APP["Next.js App (port 3000)"]
        subgraph PAGES["Pages"]
            DASH["/dashboard\nLive query feed\nBudget burn rate\nActive sessions"]
            CONN["/connections\nAdd/edit/test\ndatabase connections"]
            SCHEMA["/schema\nAnnotation editor\nPII tagging\nBlocked tables"]
            AUDIT["/audit\nFull-chain log viewer\nFilter by agent/table/time"]
            BUDGET["/budget\nPer-agent spend\nCost breakdown\nAlerts config"]
        end

        subgraph COMPONENTS["Shared Components"]
            QUERY_FEED["<QueryFeed />\nReal-time query stream\nWebSocket from gateway"]
            COST_CHART["<CostChart />\nTime-series spend\nPer-connector breakdown"]
            SCHEMA_TREE["<SchemaTree />\nTable/column browser\nInline PII toggles"]
            AUDIT_TABLE["<AuditTable />\nSearchable, filterable\nExpand to see full SQL"]
        end
    end

    subgraph GATEWAY_API["Gateway REST API (port 3100)"]
        API_CONN["GET/POST /api/connections"]
        API_SCHEMA["GET/PUT /api/schema/:conn"]
        API_AUDIT["GET /api/audit?agent=&table=&since="]
        API_BUDGET["GET /api/budget/:agent"]
        API_METRICS["GET /api/metrics (SSE stream)"]
    end

    DASH --> API_METRICS
    CONN --> API_CONN
    SCHEMA --> API_SCHEMA
    AUDIT --> API_AUDIT
    BUDGET --> API_BUDGET
```

### UI Folder Structure

```
signalpilot-ui/
├── app/
│   ├── layout.tsx                  # Shell: sidebar nav, header
│   ├── dashboard/
│   │   └── page.tsx                # Live feed + budget burn + session count
│   ├── connections/
│   │   ├── page.tsx                # Connection list
│   │   └── [id]/page.tsx           # Edit connection, test, view schema
│   ├── schema/
│   │   └── page.tsx                # Schema tree + annotation editor
│   ├── audit/
│   │   └── page.tsx                # Audit log table with filters
│   └── budget/
│       └── page.tsx                # Per-agent cost breakdown
├── components/
│   ├── query-feed.tsx              # Real-time query stream (WebSocket)
│   ├── cost-chart.tsx              # Recharts time-series
│   ├── schema-tree.tsx             # Expandable table/column tree
│   ├── audit-table.tsx             # Sortable, filterable table
│   ├── connection-form.tsx         # Add/edit connection dialog
│   └── pii-badge.tsx               # PII indicator + redaction rule selector
├── lib/
│   ├── api.ts                      # Fetch wrapper for gateway REST API
│   └── types.ts                    # Shared TypeScript types
├── Dockerfile
├── package.json
└── next.config.ts
```

### What Ships Each Day

| Day | UI Deliverable |
|-----|----------------|
| Day 2 morning | `layout.tsx` shell with sidebar nav. `/connections` page that can add a Postgres connection. |
| Day 2 afternoon | `/dashboard` with live query feed (SSE from gateway). `/audit` table rendering JSONL entries. |
| Day 3 | `/schema` annotation editor. `/budget` per-agent breakdown. Docker image builds and `docker-compose up` works end to end. |

---

## 3. DB Connector System: Project Structure

```mermaid
flowchart TB
    subgraph PROJECT_ROOT["signalpilot/"]
        CLI["cli/\nsp connect, sp serve,\nsp init"]
        GATEWAY["gateway/\nMCP server, REST API,\nSSE transport"]
        ENGINE["engine/\nSQL parser, policy check,\ncost estimation, row limits"]
        CONNECTORS["connectors/\nbase.py + one file\nper database"]
        GOV["governance/\nbudget ledger, audit log,\nPII redaction, session mgmt"]
        CONFIG["config/\nschema.yml loader,\nconnection config,\ncredential vault"]
    end

    CLI --> GATEWAY
    GATEWAY --> ENGINE
    ENGINE --> GOV
    ENGINE --> CONNECTORS
    GOV --> CONFIG
    CONNECTORS --> CONFIG
```

### Full Folder Layout

```
signalpilot/
├── pyproject.toml                      # Package metadata, dependencies, [project.scripts] entry points for uvx
├── signalpilot/
│   ├── __init__.py
│   │
│   ├── cli/                            # CLI entry points
│   │   ├── __init__.py
│   │   ├── main.py                     # Click/Typer app, `sp` command group
│   │   ├── connect.py                  # `sp connect <uri>` — register a connection
│   │   ├── serve.py                    # `sp serve <name>` — start MCP server
│   │   └── init.py                     # `sp init` — generate schema.yml from DB
│   │
│   ├── gateway/                        # MCP server + REST API
│   │   ├── __init__.py
│   │   ├── mcp_server.py              # MCP tool definitions (connect, query, etc.)
│   │   ├── rest_api.py                # FastAPI REST endpoints for UI
│   │   ├── sse.py                     # SSE transport for remote MCP + live feed
│   │   └── session.py                 # GovernanceSession — closure over state
│   │
│   ├── engine/                         # Query engine pipeline
│   │   ├── __init__.py
│   │   ├── parser.py                  # sqlglot: parse → AST → extract tables/cols
│   │   ├── validator.py               # Read-only check, statement stacking, blocked tables
│   │   ├── cost.py                    # EXPLAIN/dry-run dispatcher per connector
│   │   ├── row_limit.py              # LIMIT injection / override
│   │   └── timeout.py                # Per-query timeout with DB-side cancellation
│   │
│   ├── connectors/                     # One file per database
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseConnector ABC:
│   │   │                              #   connect, execute, estimate_cost,
│   │   │                              #   get_schema, health_check, close
│   │   ├── postgres.py                # asyncpg — Day 1
│   │   ├── duckdb.py                  # duckdb — Day 1 (local, zero-config)
│   │   ├── snowflake.py               # snowflake-connector-python — Day 3+
│   │   ├── mysql.py                   # aiomysql — Week 2+
│   │   ├── bigquery.py                # google-cloud-bigquery — Week 2+
│   │   ├── databricks.py              # databricks-sql-connector — Week 3+
│   │   ├── redshift.py                # redshift_connector — Week 3+
│   │   └── registry.py               # ConnectorRegistry.get(db_type) → connector
│   │
│   ├── governance/                     # Budget, audit, PII, sessions
│   │   ├── __init__.py
│   │   ├── budget.py                  # Per-agent/session budget ledger (SQLite)
│   │   ├── audit.py                   # Append-only JSONL audit log writer
│   │   ├── pii.py                     # Column-level redaction (hash/mask/drop)
│   │   └── session.py                # Session lifecycle: open, track, close, teardown
│   │
│   ├── config/                         # Configuration loading
│   │   ├── __init__.py
│   │   ├── schema_loader.py           # Parse schema.yml → SchemaInfo
│   │   ├── connections.py             # Load/save connection configs (~/.signalpilot/)
│   │   └── vault.py                   # Credential vault (encrypted at rest)
│   │
│   └── sandbox/                        # E2B integration (optional, only for run_analysis)
│       ├── __init__.py
│       ├── manager.py                 # Create/kill/pause E2B sandboxes
│       ├── cost.py                    # Derive sandbox cost from timestamps + formula
│       └── agent.py                   # In-VM signalpilot.sandbox_agent process
│
├── tests/
│   ├── test_parser.py                  # SQL validation: read-only, stacking, blocked
│   ├── test_connectors.py             # Connector interface compliance
│   ├── test_governance.py             # Budget, PII, audit
│   ├── test_engine.py                 # Full pipeline: parse → validate → execute
│   └── benchmarks/                     # Spider 2.0 benchmark harness (see section 4)
│       ├── spider2_runner.py
│       ├── eval.py
│       └── improve.py
│
├── docker/
│   ├── Dockerfile.gateway              # Gateway container
│   ├── Dockerfile.ui                   # Next.js UI container
│   └── docker-compose.yml             # Both containers + optional Postgres for testing
│
└── e2b/
    ├── e2b.toml                        # E2B template config
    └── e2b.Dockerfile                  # Custom sandbox template
```

### Connector Interface (Day 1 — the contract everything builds on)

```mermaid
flowchart LR
    subgraph BASE["base.py — BaseConnector ABC"]
        CONNECT["connect(config)"]
        EXECUTE["execute(sql, params)"]
        ESTIMATE["estimate_cost(sql)"]
        GET_SCHEMA["get_schema(refresh?)"]
        HEALTH["health_check()"]
        CLOSE["close()"]
    end

    subgraph POSTGRES["postgres.py"]
        PG_CONNECT["asyncpg pool"]
        PG_EXECUTE["pool.fetch()"]
        PG_ESTIMATE["EXPLAIN (FORMAT JSON)"]
        PG_SCHEMA["information_schema"]
    end

    subgraph DUCKDB["duckdb.py"]
        DUCK_CONNECT["duckdb.connect()"]
        DUCK_EXECUTE[".execute().fetchdf()"]
        DUCK_ESTIMATE["EXPLAIN → row est"]
        DUCK_SCHEMA["information_schema"]
    end

    BASE --> POSTGRES
    BASE --> DUCKDB
```

### Data Flow Through the Engine (Day 1)

```mermaid
flowchart TD
    AGENT["AI Agent calls\nquery_database(sql)"]
    PARSE["1. parser.py\nParse SQL → AST\nExtract tables, columns"]
    VALIDATE["2. validator.py\nRead-only? ✓\nStatement stacking? ✗\nBlocked tables? ✗"]
    COST["3. cost.py\nEXPLAIN / dry-run\nCompare to budget"]
    ROW_LIMIT["4. row_limit.py\nInject LIMIT if missing\nCap if over max"]
    EXECUTE["5. connector.execute(sql)\nWith statement_timeout"]
    PII["6. pii.py\nRedact flagged columns\nhash / mask / drop"]
    AUDIT["7. audit.py\nWrite full chain\nto audit.jsonl"]
    RETURN["Return governed\nresult to agent"]

    AGENT --> PARSE
    PARSE -->|"pass"| VALIDATE
    PARSE -->|"parse error"| BLOCK1["Block + log"]
    VALIDATE -->|"pass"| COST
    VALIDATE -->|"DDL/DML/stacking"| BLOCK2["Block + log"]
    COST -->|"under budget"| ROW_LIMIT
    COST -->|"over budget"| BLOCK3["Block + log"]
    ROW_LIMIT --> EXECUTE
    EXECUTE --> PII
    PII --> AUDIT
    AUDIT --> RETURN
```

---

## 4. Benchmarking: Spider 2.0 + Recursive Improvement Loop

### What Is Spider 2.0?

Spider 2.0 is the industry-standard text-to-SQL benchmark. ~1,000 complex natural-language questions against real-world databases. It's what every text-to-SQL system is evaluated against. If we can show that SignalPilot governance **improves** accuracy (not just safety), that's our killer competitive claim.

### What We Measure

| Metric | What It Proves | How We Measure |
|--------|---------------|----------------|
| **Execution Accuracy (EX)** | Generated SQL returns the correct result set | Compare output rows to Spider 2.0 gold-standard answers |
| **Exact Match (EM)** | Generated SQL exactly matches the gold SQL | AST-level comparison (normalized) |
| **Governance Safety Rate** | % of dangerous queries correctly blocked | Inject known-bad queries (DROP, stacking), measure block rate |
| **False Positive Rate** | % of valid queries incorrectly blocked | Measure how often the parser rejects queries it should allow |
| **Cost Reduction** | Lower DB spend per correct answer | Compare total EXPLAIN cost with vs without SignalPilot (caching, dedup, sampling) |
| **Schema Accuracy Lift** | Do annotations improve text-to-SQL accuracy? | Run benchmark with and without schema.yml annotations, compare EX |

### The Benchmark Harness

```mermaid
flowchart TB
    subgraph SPIDER["Spider 2.0 Dataset"]
        QUESTIONS["1,000 NL questions\n+ gold SQL answers\n+ database schemas"]
    end

    subgraph HARNESS["Benchmark Runner (tests/benchmarks/)"]
        RUNNER["spider2_runner.py"]
        LLM["LLM generates SQL\n(Claude / GPT / open-source)"]
        SP_GATE["SignalPilot Gateway\n(validates, estimates, executes)"]
        EVAL["eval.py\nCompare results\nto gold standard"]
    end

    subgraph METRICS["Metrics Output"]
        EX["Execution Accuracy"]
        EM["Exact Match"]
        SAFETY["Safety Rate"]
        FP["False Positive Rate"]
        COST_M["Cost per Correct Answer"]
        LIFT["Schema Annotation Lift"]
    end

    subgraph IMPROVE["Improvement Loop"]
        ANALYZE["Failure Analysis\nWhy did this query fail?"]
        ANNOTATE["Auto-annotate schema\nAdd missing descriptions"]
        TUNE_PARSER["Tune parser rules\nReduce false positives"]
        TUNE_PROMPT["Improve system prompt\nBetter SQL generation hints"]
        RERUN["Re-run benchmark\nMeasure delta"]
    end

    QUESTIONS --> RUNNER
    RUNNER --> LLM
    LLM -->|"generated SQL"| SP_GATE
    SP_GATE -->|"governed result"| EVAL
    EVAL --> METRICS

    METRICS --> ANALYZE
    ANALYZE --> ANNOTATE
    ANALYZE --> TUNE_PARSER
    ANALYZE --> TUNE_PROMPT
    ANNOTATE --> RERUN
    TUNE_PARSER --> RERUN
    TUNE_PROMPT --> RERUN
    RERUN -->|"loop"| RUNNER
```

### Recursive Agentic Improvement Loop

This is the core idea: use an LLM agent to analyze benchmark failures and automatically propose fixes. Then re-run the benchmark to verify the fixes actually improve scores. Repeat.

```mermaid
flowchart LR
    RUN["Run Benchmark\n(N questions)"]
    FAILURES["Collect Failures\n(wrong answer, blocked\ngood query, missed\nbad query)"]
    AGENT["Improvement Agent\n(Claude analyzes failures)"]
    CHANGES["Proposed Changes:\n• Schema annotations\n• Parser rule tweaks\n• Prompt adjustments\n• New test cases"]
    VALIDATE["Validate Changes\n(unit tests pass?\nno regressions?)"]
    RERUN["Re-run Benchmark\n(same N questions)"]
    COMPARE["Compare Scores\n(EX, EM, Safety, FP)\nAccept if improved,\nrevert if regressed"]

    RUN --> FAILURES
    FAILURES --> AGENT
    AGENT --> CHANGES
    CHANGES --> VALIDATE
    VALIDATE -->|"pass"| RERUN
    VALIDATE -->|"fail"| AGENT
    RERUN --> COMPARE
    COMPARE -->|"improved"| RUN
    COMPARE -->|"regressed"| AGENT
```

### Failure Categories the Agent Analyzes

```mermaid
flowchart TB
    FAILURE["Benchmark Failure"]

    FAILURE --> WRONG_TABLE["Wrong Table Selected\nFix: Add schema annotation\n'fact_revenue is the source\nof truth for board reporting'"]
    FAILURE --> WRONG_COL["Wrong Column Used\nFix: Add column description\n'revenue_amount = ARR\nexcluding one-time fees'"]
    FAILURE --> BLOCKED_GOOD["Valid Query Blocked\nFix: Relax parser rule\nor whitelist pattern"]
    FAILURE --> MISSED_BAD["Dangerous Query Allowed\nFix: Add parser rule\nor blocked_tables entry"]
    FAILURE --> TIMEOUT_Q["Query Timed Out\nFix: Add LIMIT, suggest\nindex, or flag as too broad"]
    FAILURE --> COST_OVER["Cost Over Budget\nFix: Suggest sampling,\nadd caching rule,\nor pre-aggregate"]
```

### Benchmark File Structure

```
tests/benchmarks/
├── spider2_runner.py       # Main harness:
│                           #   1. Load Spider 2.0 dataset
│                           #   2. For each question:
│                           #      a. Send NL question to LLM
│                           #      b. LLM generates SQL
│                           #      c. Pass SQL through SignalPilot gateway
│                           #      d. Execute against test DB
│                           #      e. Compare result to gold answer
│                           #   3. Output metrics JSON
│
├── eval.py                 # Evaluation functions:
│                           #   - execution_accuracy(result, gold)
│                           #   - exact_match(sql, gold_sql)
│                           #   - safety_rate(blocked, should_block)
│                           #   - false_positive_rate(blocked, should_allow)
│                           #   - cost_per_correct(costs, correct_count)
│
├── improve.py              # Improvement agent:
│                           #   1. Load failure report from last run
│                           #   2. Classify each failure
│                           #   3. Generate proposed changes:
│                           #      - Schema annotation patches (YAML)
│                           #      - Parser rule additions
│                           #      - System prompt edits
│                           #   4. Apply changes to a branch
│                           #   5. Re-run benchmark
│                           #   6. Accept/revert based on delta
│
├── datasets/               # Spider 2.0 data
│   ├── questions.json      # NL questions + gold SQL
│   ├── schemas/            # Database schemas for each Spider DB
│   └── databases/          # SQLite/DuckDB copies of Spider DBs
│
├── results/                # Benchmark run outputs
│   ├── run_001.json        # Metrics + per-question results
│   ├── run_002.json
│   └── comparison.md       # Auto-generated delta report
│
└── annotations/            # Schema annotations for Spider DBs
    ├── college_2.yml       # Annotations for Spider's college_2 database
    ├── car_1.yml
    └── ...                 # One per Spider database
```

### The Competitive Claim

After running the improvement loop 3-5 times, we should be able to make this claim:

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  "Text-to-SQL with SignalPilot governance + schema annotations      │
│   scores X% higher on Spider 2.0 execution accuracy than raw        │
│   LLM-generated SQL — while blocking 100% of dangerous queries      │
│   and reducing database costs by Y%."                               │
│                                                                     │
│  This is not a tradeoff between safety and accuracy.                │
│  Governance IMPROVES accuracy because the LLM gets better           │
│  context (annotations) and the system catches bad queries           │
│  before they corrupt results.                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 72-Hour Execution Plan

### Day 1 (Monday) — Skeleton + Core Engine

| Block | Hours | Deliverable | Files |
|-------|-------|-------------|-------|
| Morning | 3h | Project scaffold: `pyproject.toml`, folder structure, `BaseConnector` ABC, `PostgresConnector`, `DuckDBConnector` | `connectors/base.py`, `postgres.py`, `duckdb.py`, `registry.py` |
| Morning | 2h | SQL parser + validator: read-only enforcement, statement stacking detection, blocked table check | `engine/parser.py`, `engine/validator.py` |
| Afternoon | 2h | Audit log writer (JSONL) + budget ledger (SQLite) + PII redactor | `governance/audit.py`, `budget.py`, `pii.py` |
| Afternoon | 2h | MCP server with `query_database`, `list_tables`, `describe_table` tools over stdio | `gateway/mcp_server.py` |
| Evening | 1h | CLI entry points: `sp connect postgres://...` + `sp serve <name>`, wired via `[project.scripts]` so `uvx signalpilot connect` and `uvx signalpilot serve` work | `cli/connect.py`, `cli/serve.py` |
| **EOD test** | — | `uvx signalpilot connect` to a local Postgres, `uvx signalpilot serve` pipes MCP to Claude Code, Claude queries the database through SignalPilot | — |

### Day 2 (Tuesday) — Docker + UI Shell + SSE

| Block | Hours | Deliverable | Files |
|-------|-------|-------------|-------|
| Morning | 2h | SSE transport for gateway (remote MCP + live query feed) | `gateway/sse.py`, `gateway/rest_api.py` |
| Morning | 2h | `Dockerfile.gateway` + `docker-compose.yml` | `docker/` |
| Afternoon | 3h | Next.js UI: layout shell, `/connections` page, `/dashboard` with live query feed | `signalpilot-ui/app/` |
| Afternoon | 2h | `/audit` log viewer, `/budget` summary | `signalpilot-ui/app/audit/`, `budget/` |
| Evening | 1h | `Dockerfile.ui` + wire into compose | `docker/Dockerfile.ui` |
| **EOD test** | — | `docker-compose up` → gateway + UI running. Connect to Postgres. Query from Claude Code. See queries appear live in the UI dashboard. | — |

### Day 3 (Wednesday) — Benchmark + Improvement Loop

| Block | Hours | Deliverable | Files |
|-------|-------|-------------|-------|
| Morning | 2h | Download Spider 2.0 dataset, load into DuckDB/SQLite test databases | `tests/benchmarks/datasets/` |
| Morning | 2h | Benchmark runner: NL → LLM → SQL → SignalPilot → execute → compare to gold | `tests/benchmarks/spider2_runner.py`, `eval.py` |
| Afternoon | 2h | First benchmark run: baseline scores (EX, EM, Safety, FP, Cost) | `tests/benchmarks/results/run_001.json` |
| Afternoon | 2h | Write schema annotations for 10 Spider databases. Re-run. Measure lift. | `tests/benchmarks/annotations/` |
| Evening | 2h | Improvement agent: analyze failures, propose annotation/parser changes, re-run, compare | `tests/benchmarks/improve.py` |
| **EOD test** | — | Publish `comparison.md` showing baseline vs annotated vs agent-improved scores. First evidence of the recursive improvement loop working. | — |

---

## Docker Compose: What Ships Day 2

```yaml
# docker/docker-compose.yml
services:
  gateway:
    build:
      context: ..
      dockerfile: docker/Dockerfile.gateway
    ports:
      - "3100:3100"        # REST API + SSE for UI
    environment:
      - SP_CONNECTIONS_DIR=/data/connections
      - SP_AUDIT_DIR=/data/audit
    volumes:
      - sp-data:/data
    command: signalpilot serve --sse --port 3100

  ui:
    build:
      context: ../signalpilot-ui
      dockerfile: Dockerfile
    ports:
      - "3000:3000"        # Next.js dashboard
    environment:
      - NEXT_PUBLIC_GATEWAY_URL=http://gateway:3100
    depends_on:
      - gateway

  # Optional: test Postgres for local dev
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: testpass
      POSTGRES_DB: testdb
    ports:
      - "5432:5432"

volumes:
  sp-data:
```

---

## Success Criteria: End of 72 Hours

| Checkpoint | Verified By |
|-----------|-------------|
| `uvx signalpilot connect` registers a Postgres connection | CLI test |
| `uvx signalpilot serve` starts an MCP server, Claude Code can query through it | `claude mcp add signalpilot -- uvx signalpilot serve prod-analytics` |
| SQL parser blocks `DROP TABLE`, `INSERT`, statement stacking | `test_parser.py` passes |
| Audit log writes every query with full chain | Inspect `~/.signalpilot/audit.jsonl` |
| `docker-compose up` starts gateway + UI | Docker test |
| UI shows live query feed at `localhost:3000` | Browser test |
| Spider 2.0 benchmark runs and produces metrics JSON | `spider2_runner.py` completes |
| Schema annotations improve Spider execution accuracy by measurable delta | `comparison.md` shows lift |
| Improvement agent proposes at least one change that improves scores | `improve.py` produces accepted patch |
