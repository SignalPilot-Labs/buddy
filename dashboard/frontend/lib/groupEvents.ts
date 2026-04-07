import type { FeedEvent, GroupedEvent, ToolCall } from "@/lib/types";
import { getToolCategory, type ToolCategory } from "@/lib/types";
import { milestoneFromAudit } from "@/lib/groupEventsHelpers";

export type { GroupedEvent } from "@/lib/types";
export { extractReadFiles, extractReadPaths, extractEditSummary, extractBashCommands } from "@/lib/groupEventsHelpers";

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

function getTs(e: FeedEvent): number {
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

  // ── Pass 2: Match Agent tool calls to their subagent children via temporal matching ──
  const agentCallToChildren = new Map<string, ToolCall[]>();
  const agentCalls: { toolUseId: string; ts: number }[] = [];
  for (const ev of events) {
    if (ev._kind === "tool" && getToolCategory(ev.data.tool_name) === AGENT_CATEGORY && ev.data.tool_use_id) {
      agentCalls.push({ toolUseId: ev.data.tool_use_id, ts: new Date(ev.data.ts).getTime() });
    }
  }
  agentCalls.sort((a, b) => a.ts - b.ts);
  const claimedAgentIds = new Set<string>();
  for (const ac of agentCalls) {
    let bestAid: string | null = null;
    let bestDelta = Infinity;
    for (const [aid, tools] of subagentTools) {
      if (claimedAgentIds.has(aid)) continue;
      const firstToolTs = new Date(tools[0].ts).getTime();
      const delta = firstToolTs - ac.ts;
      if (delta >= -2000 && delta < bestDelta) {
        bestDelta = delta;
        bestAid = aid;
      }
    }
    if (bestAid) {
      agentCallToChildren.set(ac.toolUseId, subagentTools.get(bestAid)!);
      claimedAgentIds.add(bestAid);
    }
  }

  // ── Pass 3: Collect subagent_complete audit events for final text ──
  const subagentFinalTexts = new Map<string, string>();
  for (const ev of events) {
    if (ev._kind === "audit" && ev.data.event_type === "subagent_complete") {
      const tuid = ev.data.details?.tool_use_id as string;
      const text = ev.data.details?.final_text as string;
      if (tuid && text) subagentFinalTexts.set(tuid, text);
    }
  }

  const subagentTypes = new Map<string, string>();
  for (const ev of events) {
    if (ev._kind === "audit" && ev.data.event_type === "subagent_start") {
      const tuid = ev.data.details?.tool_use_id as string;
      const agentType = ev.data.details?.agent_type as string;
      if (tuid && agentType) subagentTypes.set(tuid, agentType);
    }
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
        result.push({ type: "llm_message", role, text, thinking, ts });
      }
      continue;
    }

    // ── Usage: Collapse into a single tick (take the last one in a burst) ──
    if (ev._kind === "usage") {
      let lastUsage = ev.data;
      i++;
      while (i < events.length && events[i]._kind === "usage") {
        lastUsage = (events[i] as { _kind: "usage"; data: typeof lastUsage }).data;
        i++;
      }
      result.push({
        type: "usage_tick",
        data: {
          input_tokens: lastUsage.input_tokens,
          output_tokens: lastUsage.output_tokens,
          total_input: lastUsage.total_input_tokens,
          total_output: lastUsage.total_output_tokens,
          cache_read: lastUsage.cache_read_input_tokens,
        },
        ts: lastUsage.ts,
      });
      continue;
    }

    // ── Control events ──
    if (ev._kind === "control") {
      result.push({ type: "control", text: ev.text, ts: ev.ts });
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

      // Agent calls: attach their subagent's child tools and final text
      if (cat === AGENT_CATEGORY) {
        const children = (tc.tool_use_id && agentCallToChildren.get(tc.tool_use_id)) || [];
        const finalText = (tc.tool_use_id && subagentFinalTexts.get(tc.tool_use_id)) || "";
        const agentType = (tc.tool_use_id && subagentTypes.get(tc.tool_use_id)) || "";
        result.push({ type: "agent_run", tool: tc, childTools: children, finalText, agentType, ts: tc.ts });
        i++;
        continue;
      }

      // Session gate is a milestone
      if (cat === "session_gate") {
        result.push({ type: "milestone", label: "End Session", detail: "", color: "#ffffff", ts: tc.ts });
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

        if (batch.length === 1) {
          result.push({ type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const label = cat === "read"
            ? `Read ${batch.length} files`
            : cat === "glob"
              ? `Searched ${batch.length} patterns`
              : cat === "grep"
                ? `Grep ${batch.length} searches`
                : `${batch.length} ${cat} calls`;
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ type: "tool_group", category: cat, label, tools: batch, ts: batch[0].ts, totalDuration });
        }
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

        if (batch.length === 1) {
          result.push({ type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ type: "edit_group", tools: batch, ts: batch[0].ts, totalDuration });
        }
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

        if (batch.length === 1) {
          result.push({ type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ type: "bash_group", tools: batch, ts: batch[0].ts, totalDuration });
        }
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

        if (batch.length === 1) {
          result.push({ type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ type: "playwright_group", tools: batch, ts: batch[0].ts, totalDuration });
        }
        continue;
      }

      // Everything else: single tool
      result.push({ type: "single_tool", tool: tc, ts: tc.ts });
      continue;
    }

    // Fallback: skip unknown
    i++;
  }

  return result;
}
