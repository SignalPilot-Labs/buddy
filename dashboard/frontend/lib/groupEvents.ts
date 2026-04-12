import type { FeedEvent, ToolCall } from "./types";
import { getToolCategory, type ToolCategory } from "./types";
import { milestoneFromAudit, type GroupedEvent } from "./groupEventHelpers";
export type { GroupedEvent } from "./groupEventHelpers";

/* ── Grouping Logic ── */

const GROUPABLE_CATEGORIES = new Set<ToolCategory>(["read", "glob", "grep", "web_search", "tool_search"]);
const EDIT_CATEGORIES = new Set<ToolCategory>(["edit", "write"]);
const BASH_CATEGORY: ToolCategory = "bash";
const PLAYWRIGHT_CATEGORIES = new Set<ToolCategory>([
  "playwright_navigate", "playwright_screenshot", "playwright_snapshot",
  "playwright_click", "playwright_form", "playwright_type", "playwright_evaluate"
]);
const AGENT_CATEGORY: ToolCategory = "agent";

// Time window for grouping consecutive same-type tools (ms)
const GROUP_WINDOW = 30_000;

export function getTs(e: FeedEvent): number {
  if (e._kind === "tool") return new Date(e.data.ts).getTime();
  if (e._kind === "audit") return new Date(e.data.ts).getTime();
  if (e._kind === "usage") return new Date(e.data.ts).getTime();
  return new Date(e.ts).getTime();
}

export function groupEvents(events: FeedEvent[]): GroupedEvent[] {
  // ── Pass 1: Group subagent tool calls by agent_id ──
  // Tools with agent_id != null are subagent tools — they render inside their Agent card
  const subagentTools = new Map<string, ToolCall[]>();
  const subagentToolIds = new Set<number>();
  for (const ev of events) {
    if (ev._kind === "tool" && ev.data.agent_id) {
      const aid = ev.data.agent_id;
      if (!subagentTools.has(aid)) subagentTools.set(aid, []);
      subagentTools.get(aid)!.push(ev.data);
      subagentToolIds.add(ev.data.id);
    }
  }

  // ── Pass 2: Build deterministic agent_id → parent_tool_use_id map from audits ──
  // The backend tracks Agent PreToolUse → SubagentStart 1:1 via a FIFO queue
  // and persists parent_tool_use_id in the subagent_start / subagent_complete
  // audit events, giving us an authoritative link. We also collect the
  // subagent's type (from start) and last_assistant_message (from complete)
  // keyed by the parent tool_use_id for rendering inside the Agent card.
  const agentIdToParentTuid = new Map<string, string>();
  const subagentTypes = new Map<string, string>();
  const subagentFinalTexts = new Map<string, string>();
  for (const ev of events) {
    if (ev._kind !== "audit") continue;
    const details = ev.data.details;
    if (!details) continue;
    if (ev.data.event_type === "subagent_start") {
      const parentTuid = details.parent_tool_use_id as string;
      const agentId = details.agent_id as string;
      const agentType = details.agent_type as string;
      if (parentTuid && agentId) agentIdToParentTuid.set(agentId, parentTuid);
      if (parentTuid && agentType) subagentTypes.set(parentTuid, agentType);
    } else if (ev.data.event_type === "subagent_complete") {
      const parentTuid = details.parent_tool_use_id as string;
      const text = details.final_text as string;
      if (parentTuid && text) subagentFinalTexts.set(parentTuid, text);
    }
  }

  // ── Pass 3: Attribute subagent tool groups to their parent Agent tool call ──
  // Keyed by the Task tool_use_id, populated from the authoritative audit link above.
  const agentCallToChildren = new Map<string, ToolCall[]>();
  for (const [agentId, tools] of subagentTools) {
    const parentTuid = agentIdToParentTuid.get(agentId);
    if (parentTuid) agentCallToChildren.set(parentTuid, tools);
  }

  const result: GroupedEvent[] = [];
  let i = 0;

  while (i < events.length) {
    const ev = events[i];

    // Skip subagent lifecycle audit events — consumed by agent card
    if (ev._kind === "audit" && (ev.data.event_type === "subagent_start" || ev.data.event_type === "subagent_complete")) {
      i++;
      continue;
    }

    // Skip subagent tools — shown inside their Agent card
    if (ev._kind === "tool" && subagentToolIds.has(ev.data.id)) {
      i++;
      continue;
    }

    // ── LLM Text: Accumulate consecutive same-role text + thinking ──
    if (ev._kind === "llm_text" || ev._kind === "llm_thinking") {
      let text = "";
      let thinking = "";
      const role = ev.agent_role || "worker";
      const ts = ev.ts;

      while (i < events.length) {
        const cur = events[i];
        if (cur._kind === "llm_text" && (cur.agent_role || "worker") === role) {
          text += cur.text;
          i++;
        } else if (cur._kind === "llm_thinking" && (cur.agent_role || "worker") === role) {
          thinking += cur.text;
          i++;
        } else {
          break;
        }
      }

      if (text || thinking) {
        result.push({ id: `llm-${ts}-${role}`, type: "llm_message", role, text, thinking, ts });
      }
      continue;
    }

    // ── Usage: skip from feed (data consumed by StatsBar, not shown in feed) ──
    if (ev._kind === "usage") {
      i++;
      continue;
    }

    // ── Control events ──
    if (ev._kind === "control") {
      result.push({ id: `ctrl-${ev.ts}-${ev.text.slice(0, 20)}`, type: "control", text: ev.text, ts: ev.ts, retryAction: ev.retryAction });
      i++;
      continue;
    }

    // ── Audit events → milestones or skip ──
    if (ev._kind === "audit") {
      const milestone = milestoneFromAudit(ev);
      if (milestone) result.push(milestone);
      i++;
      continue;
    }

    // ── Tool calls: Group by category ──
    if (ev._kind === "tool") {
      const tc = ev.data;
      const cat = getToolCategory(tc.tool_name);
      const tsMs = getTs(ev);

      // Agent calls: attach their subagent's child tools and final text.
      // An orphan post (phase="post" with no input_data) is a PostToolUseFailure
      // or merge-failure artifact — not a real Task invocation. Skip it to avoid
      // rendering a phantom "Sub-agent task" card. A legitimate merged Agent
      // event retains its pre-phase input_data even after phase becomes "post".
      if (cat === AGENT_CATEGORY) {
        if (tc.phase === "post" && !tc.input_data) {
          i++;
          continue;
        }
        const children = (tc.tool_use_id && agentCallToChildren.get(tc.tool_use_id)) || [];
        const finalText = (tc.tool_use_id && subagentFinalTexts.get(tc.tool_use_id)) || "";
        const agentType = (tc.tool_use_id && subagentTypes.get(tc.tool_use_id)) || "";
        result.push({ id: `agent-${tc.id}`, type: "agent_run", tool: tc, childTools: children, finalText, agentType, ts: tc.ts });
        i++;
        continue;
      }

      // Session gate is a milestone
      if (cat === "session_gate") {
        result.push({ id: `ms-${tc.ts}-End Session`, type: "milestone", label: "End Session", detail: "", color: "#ffffff", ts: tc.ts });
        i++;
        continue;
      }

      // Collect consecutive same-category tools
      const batch: ToolCall[] = [tc];
      i++;

      // For groupable categories (reads, globs, greps, searches)
      if (GROUPABLE_CATEGORIES.has(cat)) {
        while (i < events.length) {
          const next = events[i];
          if (next._kind !== "tool") break;
          const nextCat = getToolCategory(next.data.tool_name);
          if (nextCat !== cat) break;
          if (Math.abs(new Date(next.data.ts).getTime() - tsMs) > GROUP_WINDOW) break;
          batch.push(next.data);
          i++;
        }

        const label = cat === "read"
          ? `Read ${batch.length} file${batch.length !== 1 ? "s" : ""}`
          : cat === "glob"
            ? `Searched ${batch.length} pattern${batch.length !== 1 ? "s" : ""}`
            : cat === "grep"
              ? `Grep ${batch.length} search${batch.length !== 1 ? "es" : ""}`
              : `${batch.length} ${cat} call${batch.length !== 1 ? "s" : ""}`;
        const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
        result.push({ id: `tg-${batch[0].id}`, type: "tool_group", category: cat, label, tools: batch, ts: batch[0].ts, totalDuration });
        continue;
      }

      // Edit/Write groups
      if (EDIT_CATEGORIES.has(cat)) {
        while (i < events.length) {
          const next = events[i];
          if (next._kind !== "tool") break;
          const nextCat = getToolCategory(next.data.tool_name);
          if (!EDIT_CATEGORIES.has(nextCat)) break;
          if (Math.abs(new Date(next.data.ts).getTime() - tsMs) > GROUP_WINDOW) break;
          batch.push(next.data);
          i++;
        }

        const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
        result.push({ id: `eg-${batch[0].id}`, type: "edit_group", tools: batch, ts: batch[0].ts, totalDuration });
        continue;
      }

      // Bash groups
      if (cat === BASH_CATEGORY) {
        while (i < events.length) {
          const next = events[i];
          if (next._kind !== "tool") break;
          if (getToolCategory(next.data.tool_name) !== BASH_CATEGORY) break;
          if (Math.abs(new Date(next.data.ts).getTime() - tsMs) > GROUP_WINDOW) break;
          batch.push(next.data);
          i++;
        }

        const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
        result.push({ id: `bg-${batch[0].id}`, type: "bash_group", tools: batch, ts: batch[0].ts, totalDuration });
        continue;
      }

      // Playwright groups
      if (PLAYWRIGHT_CATEGORIES.has(cat)) {
        while (i < events.length) {
          const next = events[i];
          if (next._kind !== "tool") break;
          if (!PLAYWRIGHT_CATEGORIES.has(getToolCategory(next.data.tool_name))) break;
          if (Math.abs(new Date(next.data.ts).getTime() - tsMs) > GROUP_WINDOW) break;
          batch.push(next.data);
          i++;
        }

        const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
        result.push({ id: `pg-${batch[0].id}`, type: "playwright_group", tools: batch, ts: batch[0].ts, totalDuration });
        continue;
      }

      // Everything else: single tool
      result.push({ id: `st-${tc.id}`, type: "single_tool", tool: tc, ts: tc.ts });
      continue;
    }

    // Fallback: skip unknown
    i++;
  }

  return _insertCommitDividers(result);
}

const ROUND_PATTERN = /\[Round\s+(\d+)\]/i;

function _insertCommitDividers(groups: GroupedEvent[]): GroupedEvent[] {
  /** Insert a divider after any bash tool that runs git commit. */
  const out: GroupedEvent[] = [];
  for (const gev of groups) {
    out.push(gev);
    const commitRound = _detectGitCommit(gev);
    if (commitRound !== null) {
      const roundLabel = commitRound > 0 ? `Round ${commitRound}` : "Round";
      const label = `${roundLabel} complete`;
      out.push({ id: `div-${gev.ts}-${label}`, type: "divider", label, ts: gev.ts });
    }
  }
  return out;
}

function _detectGitCommit(gev: GroupedEvent): number | null {
  /** Check if a grouped event contains a git commit. Returns round number or 0 if unknown. */
  const commands = _extractCommands(gev);
  for (const cmd of commands) {
    if (!cmd.includes("git commit") && !cmd.includes("git -c") ) continue;
    if (!cmd.includes("commit")) continue;
    const match = cmd.match(ROUND_PATTERN);
    if (match) return parseInt(match[1], 10);
    return 0;
  }
  return null;
}

function _extractCommands(gev: GroupedEvent): string[] {
  /** Extract command strings from bash groups. */
  if (gev.type === "bash_group") {
    return gev.tools.map((t) => (t.input_data?.command as string) || "");
  }
  return [];
}
