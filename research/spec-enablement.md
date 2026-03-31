# SignalPilot: Product Enablement Spec
**For investors, executives, and design partners.**

> Every AI company needs their agents to query databases.
> None of them can do it safely.
> SignalPilot is the infrastructure that makes it possible.

---

## The Market in 30 Seconds

AI agents are connecting to production databases at explosive scale. MCP (the protocol every AI agent now speaks) hit **97M monthly SDK downloads** and **12,000+ servers**. OpenAI, Google, Microsoft, and Anthropic all adopted it.

But there is **no governance layer between the agent and the database.** The official Anthropic Postgres MCP server was archived after a SQL injection let anyone bypass read-only mode and run `DROP SCHEMA public CASCADE;`. Replit's agent deleted a founder's production database on live TV. Amazon's AI coding tool caused a 13-hour AWS outage. Fortune 500 companies collectively leaked **$400M in unbudgeted cloud spend** from agent loops.

**E2B proved that "AI sandbox" is a $32M+ funded, 88%-of-Fortune-100 market.** But E2B sandboxes code execution. Nobody sandboxes database access. SignalPilot does.

---

## Who Uses This and Why

### Persona 1: The AI App Builder
*"I'm building an AI product that needs to query customer data."*

**Today (E2B / raw MCP):** They connect their AI agent to the database with a connection string. The agent can run any query -- `SELECT *` on a 10TB table, `DROP TABLE`, or return every SSN in the database. They hand-roll read-only mode that can be bypassed with one SQL statement. They have no audit trail, no cost controls, no way to limit what data the agent sees.

**With SignalPilot:**

| Feature | What It Does | What It Prevents |
|---------|-------------|-----------------|
| **Protocol-level read-only** | Blocks mutations at the wire protocol level, not just SQL transaction level | The `COMMIT; DROP SCHEMA public CASCADE;` attack that killed Anthropic's own MCP server |
| **Query cost pre-estimation** | Estimates compute cost before execution. Blocks queries above threshold. | The $5K single Snowflake query. The $47K agent loop. The $400M collective cloud leak. |
| **Row limits** | Caps result sets (e.g., max 10K rows returned to the agent) | A `SELECT *` on a billion-row table that returns PII for every customer |
| **Column redaction** | Masks sensitive columns (SSN, email, salary) before data reaches the LLM | The 26% of GenAI uploads that contain sensitive data (Harmonic Security Q3 2025) |
| **Audit log** | Logs every query: who asked, what SQL ran, what data came back, which model generated it | The "how do you track AI-generated access to customer data?" question from the auditor |
| **One command setup** | `pip install signalpilot && sp connect postgres://host/db --read-only` | The 2-6 week engineering project to hand-roll a query proxy |

**Revenue enablement:** This is what lets an AI startup ship a "talk to your data" feature without a security review blocking the launch for 3 months.

---

### Persona 2: The Data Platform Engineer
*"My CTO wants AI agents querying our warehouse. I need to make it safe."*

**Today:** They spin up a read-only replica ($2x storage cost), write a homegrown SQL parser that misses edge cases (TRUNCATE? CALL? CTEs hiding mutations?), maintain it forever, and pray. 80.9% of teams have pushed AI agents into testing/production, but only 14.4% went live with full security approval.

**With SignalPilot:**

| Feature | What It Does | What It Prevents |
|---------|-------------|-----------------|
| **Per-agent identity** | Each AI agent gets its own identity, not a shared database user | "12 different MCP servers have production credentials and nobody knows which are still active" |
| **Per-agent credit budgets** | Set a $/day or $/query cap per agent, not per warehouse | One agent burning the entire team's Snowflake budget in a single runaway loop |
| **Schema-aware policies** | Define which tables/columns each agent can access, by name | The intern's chatbot querying the `employee_compensation` table |
| **Query pre-approval** | High-cost or sensitive queries require human approval before execution | The agent that decided "the best course of action was to delete and recreate the environment" (Amazon Kiro, 13-hour AWS outage) |
| **Credential management** | Central credential store with automatic rotation. Agents never see raw connection strings. | 88% of MCP servers require credentials, 53% use static API keys "rarely rotated." 30+ CVEs in Jan-Feb 2026. |
| **Connection health monitoring** | Latency, error rates, pool utilization per connection | Silent failures where the agent retries endlessly against a degraded warehouse |

**Revenue enablement:** This is what lets the platform team say "yes" to AI adoption instead of "no" or "not yet."

---

### Persona 3: The CISO / Head of Compliance
*"We have an audit coming up. The auditor is going to ask about AI governance."*

**Today:** 90%+ of orgs have shadow AI with zero audit trails (MIT NANDA 2025). ChatGPT Enterprise logs the prompt but not the database query it generated. Snowflake logs the query but not which AI agent generated it or what the human originally asked. There is no tool that captures the full chain.

**With SignalPilot:**

| Feature | What It Does | What It Prevents |
|---------|-------------|-----------------|
| **Full-chain audit log** | Captures: human question -> AI prompt -> generated SQL -> tables/columns accessed -> rows returned -> cost -> who approved | The regulatory exam where the answer to "how do you track AI data access?" is "we don't" |
| **Compliance-mapped exports** | Audit reports that map directly to SOC 2 CC6.1, HIPAA 164.312(b), SEC 17a-4 | 3 weeks of manual evidence gathering before every audit |
| **PII detection** | Flags queries that access or return personally identifiable information | The 26% of GenAI file uploads containing sensitive data, invisible to IT |
| **Shadow AI prevention** | If all AI-to-database connections go through SignalPilot, ungoverned access is blocked | The shadow MCP deployments where orgs discover 3-10x more connections than IT expected |
| **Data residency controls** | Ensure query results stay within geographic boundaries | EU AI Act violations (penalties up to 7% global revenue, enforcement Aug 2, 2026) |

**Revenue enablement:** This is the difference between "AI is blocked pending compliance review" and "AI is live within the governance framework."

---

### Persona 4: The CEO / Investor
*"Why is this a venture-scale opportunity?"*

| Signal | Data Point | Source |
|--------|-----------|--------|
| Protocol dominance | MCP: 97M monthly SDK downloads, 12K+ servers, adopted by OpenAI/Google/Microsoft | PulseMCP, mcpevals.io |
| Proven adjacent market | E2B (code sandbox): $32M raised, 88% F100, $21M Series A | E2B/Insight Partners, July 2025 |
| Zero competition in category | GitHub search "MCP database sandbox": **0 results** | GitHub, March 2026 |
| Governance market size | $492M in 2026, >$1B by 2030 | Gartner, Feb 2026 |
| Regulatory forcing function | EU AI Act high-risk enforcement: August 2, 2026 (7% revenue penalties) | EUR-Lex |
| Enterprise readiness gap | 83% deploying AI agents, only 29% feel security-ready | Cisco, 2026 |
| Pain is front-page news | Replit DB deletion (2.7M views), $47K agent loop, Amazon 13-hr outage, $400M collective cloud leak | Fortune, FT, Engadget |
| Hiring signal | 1,400+ AI security engineer roles ($143K-$280K), 0 for "AI database sandbox" | Glassdoor/LinkedIn |
| Switching cost / moat | Every audit log entry is organizational IP. After 6 months, leaving means losing all compliance history. | -- |

---

## How SignalPilot Fits Into the Stack

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  AI AGENTS                                                      │
  │  Claude Code, Cursor, GPT, Custom Agents, Copilot, etc.       │
  │  (speak MCP)                                                    │
  └──────────────────────────┬──────────────────────────────────────┘
                             │ MCP protocol
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  SIGNALPILOT                                                    │
  │                                                                 │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
  │  │ MCP Gateway  │  │ Query Engine │  │ Governance Layer     │  │
  │  │              │  │              │  │                      │  │
  │  │ Auth         │  │ SQL parsing  │  │ Per-agent budgets    │  │
  │  │ Rate limits  │  │ Cost estim.  │  │ Schema policies      │  │
  │  │ Routing      │  │ Read-only    │  │ Audit logs           │  │
  │  │ Credentials  │  │ Row limits   │  │ Pre-approval flows   │  │
  │  │              │  │ Col redact   │  │ PII detection        │  │
  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │
  │                                                                 │
  └──────────────────────────┬──────────────────────────────────────┘
                             │ Native database protocols
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  DATABASES                                                      │
  │  Snowflake, Databricks, Postgres, BigQuery, MySQL, etc.        │
  └─────────────────────────────────────────────────────────────────┘
```

SignalPilot sits at the only chokepoint where you can enforce governance: **between the agent and the database.** Every query passes through. Every query is logged. Every query is governed.

---

## The E2B Comparison (Why This Isn't Just "E2B for Databases")

E2B proved the sandbox model works. SignalPilot goes deeper on the data layer.

| Dimension | E2B | SignalPilot |
|-----------|-----|------------|
| **What it protects** | Your servers (code execution) | Your data (database queries) |
| **Isolation model** | Firecracker microVMs (~$0.05/hr) | Protocol-level SQL interception (near-zero overhead) |
| **Understands the payload** | No -- executes any code blindly | Yes -- parses SQL, knows tables, estimates cost |
| **Cost governance** | None (you pay for compute time) | Pre-estimates query cost, blocks above threshold, per-agent budgets |
| **Audit trail** | "Code ran in sandbox" | "Analyst asked X, model generated Y SQL, query touched tables A/B, returned N rows of non-PII data, cost $0.003, auto-approved by read-only policy" |
| **Data governance** | None (sandbox doesn't know what data exists) | Column redaction, row limits, schema policies, PII detection |
| **Setup** | SDK integration + cloud account | `pip install signalpilot` + one command (local-first) |
| **MCP native** | No (compute primitive, MCP is bolt-on via Docker partnership) | Yes (exposes MCP server, acts as MCP gateway) |
| **Switching cost** | Low (swap sandbox providers easily) | High (audit history, schema annotations, compliance records are organizational IP) |

**E2B's gap is SignalPilot's wedge.** E2B's users already need database access governance -- E2B just doesn't provide it. SignalPilot is complementary, not competitive: an E2B sandbox can use SignalPilot as its database layer.

---

## Feature-to-Outcome Map

Three categories: **Ship faster**, **Analyze better**, **Spend less**.

### SHIP FASTER -- "AI features that used to be blocked now launch"

| # | Feature | This enables me to... | Which helps the company... | Without SignalPilot... |
|---|---------|----------------------|---------------------------|----------------------|
| 1 | **One-command setup** | Connect my AI agent to our production database in 30 seconds | Ship an "ask your data" feature this sprint instead of next quarter | 2-6 weeks to hand-roll a query proxy. Most teams never finish it. AI stays on sample data. |
| 2 | **Protocol-level read-only** | Give AI agents real database access without risk of data mutation | Unblock the product team waiting on "is the AI feature safe?" approval | Security review says no, or the team ships with a read-only transaction that can be bypassed (`COMMIT; DROP SCHEMA`) |
| 3 | **Credential management** | Onboard new AI tools (Cursor, Claude Code, internal agents) in minutes, not days | Adopt best-in-class AI tools as soon as they ship, not after a 3-month security review | Each new tool needs its own credentials, VPN config, SSL certs. Platform team becomes the bottleneck. |
| 4 | **Query pre-approval workflows** | Let non-technical stakeholders trigger AI data analysis with human-in-the-loop for sensitive queries | Put "talk to your data" in front of the sales team, product team, and execs -- not just analysts | Either: no guardrails (dangerous) or only technical users get access (limits adoption) |
| 5 | **Cross-platform governance** | Define one set of access rules that works across Snowflake, Postgres, and BigQuery | Run the same AI-powered analytics across the entire data stack, not just one warehouse | Each warehouse has its own governance model. Teams build separate AI integrations for each, or just pick one and ignore the rest. |

### ANALYZE BETTER -- "AI answers get more accurate and trustworthy"

| # | Feature | This enables me to... | Which helps the company... | Without SignalPilot... |
|---|---------|----------------------|---------------------------|----------------------|
| 6 | **Schema annotations** | Tag columns with business definitions ("revenue = ARR ex. one-time fees") that the AI reads when generating queries | Get the right number the first time instead of the wrong number followed by 2 hours of Slacking around to find the right table | AI queries `fact_rev_adj_v3` instead of `rpt_board_revenue`. The board deck has the wrong number. The CFO loses trust in the data team. |
| 7 | **Usage-based table ranking** | Automatically surface the most-queried tables and flag undocumented ones | Reduce "which table should I use?" confusion by 80% for new analysts and AI agents alike | New hires and AI agents guess which of 6 "revenue" tables is correct. They guess wrong. |
| 8 | **Full-chain audit log** | See exactly which tables/columns the AI touched and what SQL it generated for every answer | Verify AI-generated insights before putting them in a board deck. Trace wrong numbers back to the exact query. | The AI says "revenue is $4.2M" and nobody can tell you which table, which filters, or which time range that came from. |
| 9 | **Result-set sampling** | Return a representative sample (e.g., 10K rows) instead of the full 50M-row table to the AI | Get faster AI responses, lower LLM costs (fewer tokens), and prevent context window overflow on large datasets | Agent pulls the entire table into context, hits token limits, hallucinates, or costs 10x more in API calls. |
| 10 | **Multi-source orchestration** | Ask one question that spans Snowflake (transactions), Salesforce (pipeline), and NetSuite (accounting) | Answer "what's our revenue by customer segment?" without manually exporting CSVs and joining in a spreadsheet | Analyst exports 3 CSVs, joins in Google Sheets, spends a day, gets numbers that are stale by the time they're presented. |

### SPEND LESS -- "AI that pays for itself instead of surprising you with bills"

| # | Feature | This enables me to... | Which helps the company... | Without SignalPilot... |
|---|---------|----------------------|---------------------------|----------------------|
| 11 | **Query cost pre-estimation** | See "this query will cost ~$340 on Snowflake" before it runs, auto-block above threshold | Control AI-driven warehouse spend the same way you control cloud compute spend | A `SELECT *` on a 10TB table runs, costs $5K, nobody knew until the invoice. Snowflake resource monitors only fire after credits are burned. |
| 12 | **Per-agent credit budgets** | Set a $/day cap per AI agent ("this chatbot can spend max $50/day on Snowflake") | Forecast AI infrastructure costs, attribute spend to products/teams, and kill runaway loops before they cost $47K | One agent in a recursive loop burns the entire team's monthly Snowflake budget over a weekend. Dashboards show "healthy activity." |
| 13 | **Connection health monitoring** | See latency, error rates, and pool utilization per database connection in real time | Spot degraded warehouse performance before it cascades into failed AI features and user complaints | The AI feature is slow and nobody knows if it's the model, the network, or the warehouse. 3 teams debug in parallel for 2 days. |
| 14 | **Caching + deduplication** | Avoid re-querying the same data when multiple agents or users ask similar questions | Cut warehouse compute costs 30-60% on repeat queries (AI agents are repetitive by nature) | 10 agents ask "what's this quarter's revenue?" and each one runs the same $2 Snowflake query independently. That's $20/hr, $480/day, $14K/month for one question. |
| 15 | **Shadow AI detection** | See every AI-to-database connection across the org, including ones IT didn't approve | Eliminate redundant AI tools (most companies discover 3-10x more AI deployments than they knew about) and consolidate spend | 5 teams each pay for their own AI analytics tool, each with its own database connection, each generating its own Snowflake bill. Nobody has the full picture. |

### The Compound Effect

The features above aren't independent. They compound:

```
  One-command setup
    → More teams adopt AI for data analysis (not just the data team)
      → Schema annotations make those queries accurate (not just fast)
        → Audit logs make those answers trustworthy (not just accurate)
          → Cost controls make the whole thing sustainable (not just a pilot)
            → The company goes from "we have an AI chatbot"
               to "every decision is informed by real-time data"
```

**The unlock isn't "safer AI." The unlock is: every person in the company can ask a question about the business and get a trustworthy, auditable, cost-controlled answer from production data in seconds.** The security is what makes that possible without the CTO losing sleep.

---

## Pricing Model

| Tier | Price | What You Get | Target |
|------|-------|-------------|--------|
| **Free** | $0 | 1 database connection, read-only enforcement, basic audit log, 1K queries/mo | Solo developer, POC |
| **Pro** | $99/mo | Unlimited connections, query cost estimation, per-agent budgets, full audit dashboard, 50K queries/mo | Startup data team (5-20 people) |
| **Enterprise** | Custom | SSO/SAML, pre-approval workflows, compliance exports (SOC 2/HIPAA/EU AI Act), cross-platform governance, SLA, on-prem option | Regulated industries, F500 |

**Expansion mechanics:**
- Starts free with one connection (dev exploring AI + database)
- Expands to Pro when the team connects production databases
- Upgrades to Enterprise when compliance/audit requirements kick in (EU AI Act Aug 2026 is a forcing function)
- **Retention moat:** Every audit log entry, every schema annotation, every compliance report is organizational IP that doesn't transfer to a competitor

---

## The Go-To-Market Wedge

### Week 1: The CLI
```
pip install signalpilot
sp connect postgres://host/db --read-only --row-limit 10000 --timeout 30s
# MCP server on localhost. Any AI client connects. Every query logged.
```

**Acquisition channel:** The developer who Googles "how to safely let AI query my database" and finds zero answers (confirmed: 0 GitHub repos for "MCP database sandbox"). First result should be SignalPilot.

### Month 1-3: Community + Content
- Post in r/dataengineering, dbt Slack, Locally Optimistic with the open-source CLI
- Write "How Anthropic's Postgres MCP Server Got Hacked (And How To Prevent It)" -- the Datadog CVE is the best content marketing asset in the category
- Ship a "SignalPilot vs. raw database MCP" comparison showing the security/cost gap

### Month 3-6: Enterprise Pipeline
- Target the 88% of Fortune 100 already on E2B -- they have AI agents, they need database governance
- EU AI Act compliance deadline (Aug 2026) is the sales trigger: "Do you have audit trails for AI data access? No? Here."
- Design partner program with 3-5 mid-market companies in finance/healthcare

### Month 6-12: Platform
- Schema intelligence layer (business definitions injected into AI query generation)
- Multi-source orchestration (cross-database JOIN as a service)
- MCP gateway marketplace (pre-built policies for common compliance frameworks)

---

## Why Now, Not Later

```
  Aug 2024  ─── MCP launched (Anthropic)
  Mar 2025  ─── OpenAI adopts MCP
  Apr 2025  ─── 8M+ MCP downloads. Google adopts MCP.
  May 2025  ─── Anthropic Postgres MCP server: SQL injection CVE. Archived.
  Jul 2025  ─── Replit deletes SaaStr production database (Fortune).
                E2B raises $21M. Supabase MCP exfiltration (848 pts HN).
  Sep 2025  ─── Modal hits $1.1B valuation
  Oct 2025  ─── Docker/E2B partnership
  Nov 2025  ─── $47K agent loop. 97M monthly MCP SDK downloads.
  Dec 2025  ─── MCP donated to Linux Foundation. Amazon Kiro 13-hr outage.
                Claude Code wipes developer's home directory.
  Jan 2026  ─── 30+ CVEs filed against MCP servers in 8 weeks.
                OWASP publishes MCP Top 10.
  Feb 2026  ─── OpenClaw wipes Meta AI Safety Director's inbox.
                Gartner: AI governance market $492M in 2026.
  Mar 2026  ─── Claude Code destroys 2.5 years of production data.
                Snowflake finally ships Cortex cost controls (1 year late).
                AnalyticsWeek: $400M collective cloud leak from agent loops.

  >>> YOU ARE HERE <<<

  Aug 2026  ─── EU AI Act high-risk enforcement (7% revenue penalties)
  2027      ─── 50% of GenAI companies using agentic AI (Deloitte)
  2030      ─── AI governance market >$1B (Gartner)
```

The incidents are accelerating. The regulation is arriving. The tooling doesn't exist. Every month of delay is a month where someone else could ship the `pip install` moment.

---

*This document references research from: secure-sandbox-wedge.md, sp-market-research.md, sp-developer-horror-stories.md, market-research-mcp-gateway-2026.md, sp-ai-resistance-play.md, and sp-question.md.*
