import type { FeedEvent, ToolCall } from "./types";
import { getToolCategory, type ToolCategory } from "./types";
import { MS_PER_SECOND } from "./constants";
import { formatHoursMinutes } from "@/components/feed/eventCardHelpers";

/* ── Grouped Event Types ── */

export type GroupedEvent =
  | { id: string; type: "llm_message"; role: string; text: string; thinking: string; ts: string }
  | { id: string; type: "tool_group"; category: ToolCategory; label: string; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "agent_run"; tool: ToolCall; childTools: ToolCall[]; finalText: string; agentType: string; ts: string }
  | { id: string; type: "edit_group"; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "bash_group"; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "playwright_group"; tools: ToolCall[]; ts: string; totalDuration: number }
  | { id: string; type: "single_tool"; tool: ToolCall; ts: string }
  | { id: string; type: "control"; text: string; ts: string; retryAction?: () => void }
  | { id: string; type: "milestone"; label: string; detail: string; color: string; ts: string; event?: FeedEvent }
  | { id: string; type: "user_prompt"; prompt: string; ts: string; pending?: boolean; failed?: boolean }
  | { id: string; type: "divider"; label: string; ts: string };

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

function extractFilePath(tc: ToolCall): string {
  const input = tc.input_data || {};
  const output = tc.output_data || {};
  const fp = (input.file_path as string) || (output.filePath as string) || "";
  return fp.replace(/^\/home\/agentuser\/repo\//, "").replace(/^\/workspace\//, "");
}

function milestoneFromAudit(event: FeedEvent): GroupedEvent | null {
  if (event._kind !== "audit") return null;
  const d = event.data.details;
  const ts = event.data.ts;

  switch (event.data.event_type) {
    case "run_started":
      return { id: `ms-${ts}-Run Started`, type: "milestone", label: "Run Started", detail: `${d.model || "claude"} · ${d.branch || ""}`, color: "#88ccff", ts, event };
    case "round_complete":
      return null; // Legacy — superseded by round_ended below
    case "round_ended": {
      // Python round loop emits this after committing a round. Becomes the
      // "Round N complete" divider in the feed. Replaces the old main-branch
      // behavior where the divider was inferred from the agent's `git commit`
      // bash call (now gone since Python owns commits).
      const roundNum = d.round_number as number | undefined;
      const label = roundNum ? `Round ${roundNum} complete` : "Round complete";
      return { id: `div-${ts}-${label}`, type: "divider", label, ts };
    }
    case "pr_created":
      return { id: `ms-${ts}-PR Created`, type: "milestone", label: "PR Created", detail: String(d.url || ""), color: "#00ff88", ts, event };
    case "pr_failed":
      return { id: `ms-${ts}-PR Failed`, type: "milestone", label: "PR Failed", detail: String(d.error || "").slice(0, 100), color: "#ff4444", ts, event };
    case "session_ended":
      return { id: `ms-${ts}-Session Ended`, type: "milestone", label: "Session Ended", detail: `${d.changes_made || 0} changes · ${(d.elapsed_minutes as number)?.toFixed(1) || "?"}min`, color: "#88ccff", ts, event };
    case "killed":
      return { id: `ms-${ts}-Killed`, type: "milestone", label: "Killed", detail: `after ${(d.elapsed_minutes as number)?.toFixed(1) || "?"}min`, color: "#ff4444", ts, event };
    case "fatal_error":
      return { id: `ms-${ts}-Fatal Error`, type: "milestone", label: "Fatal Error", detail: String(d.error || "").slice(0, 100), color: "#ff4444", ts, event };
    case "planner_invoked":
      return { id: `ms-${ts}-Planner Invoked`, type: "milestone", label: "Planner Invoked", detail: `Round ${d.round} · ${d.tool_summary || ""}`, color: "#ff8844", ts, event };
    case "end_session_denied":
      return { id: `ms-${ts}-Session Denied`, type: "milestone", label: "Session Denied", detail: `${d.remaining_minutes || "?"}m remaining`, color: "#ffaa00", ts, event };
    case "session_unlocked":
      return { id: `ms-${ts}-Session Unlocked`, type: "milestone", label: "Session Unlocked", detail: "", color: "#00ff88", ts, event };
    case "stop_requested":
      return { id: `ms-${ts}-Stop Requested`, type: "milestone", label: "Stop Requested", detail: String(d.reason || ""), color: "#ff8844", ts, event };
    case "pause_requested":
      return { id: `ms-${ts}-Pause Requested`, type: "milestone", label: "Pause Requested", detail: "", color: "#ffaa00", ts, event };
    case "resumed":
      return { id: `ms-${ts}-Resumed`, type: "milestone", label: "Resumed", detail: String(d.via === "inject" ? "via inject" : ""), color: "#00ff88", ts, event };
    case "rate_limit_paused": {
      const resetEpoch = d.resets_at as number | undefined;
      const resetDetail = resetEpoch
        ? (() => {
            const resetDate = new Date(resetEpoch * MS_PER_SECOND);
            const diffMs = resetEpoch * MS_PER_SECOND - Date.now();
            const timeStr = resetDate.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
            if (diffMs <= 0) return `resets ${timeStr} (ready)`;
            return `resets ${timeStr} (${formatHoursMinutes(diffMs)})`;
          })()
        : (d.reason as string) || "out of credits";
      return { id: `ms-${ts}-Rate Limited`, type: "milestone", label: "Rate Limited", detail: resetDetail, color: "#ffaa00", ts, event };
    }
    case "prompt_injected":
    case "prompt_submitted":
      return { id: `up-${event.data.id}-${ts}`, type: "user_prompt", prompt: String(d.prompt || ""), ts, pending: Boolean(d._pending), failed: Boolean(d._failed) };
    case "session_resumed":
      return { id: `ms-${ts}-Session Resumed`, type: "milestone", label: "Session Resumed", detail: "", color: "#00ff88", ts, event };
    case "auto_commit":
      return { id: `ms-${ts}-Auto Commit`, type: "milestone", label: "Auto Commit", detail: String(d.reason || "").slice(0, 100), color: "#888888", ts, event };
    case "push_failed":
      return { id: `ms-${ts}-Push Failed`, type: "milestone", label: "Push Failed", detail: String(d.error || "").slice(0, 100), color: "#ff4444", ts, event };
    case "permission_denied":
      return { id: `ms-${ts}-Permission Denied`, type: "milestone", label: "Permission Denied", detail: String(d.tool_name || ""), color: "#ff4444", ts, event };
    case "run_ended":
      return { id: `ms-${ts}-Run Ended`, type: "milestone", label: "Run Ended", detail: String(d.status || ""), color: "#88ccff", ts, event };
    case "permission_allowed":
    case "subagent_stuck":
    case "subagent_timeout":
      return null; // Skip — permission_allowed too frequent, subagent_stuck/subagent_timeout not currently emitted
    case "sdk_config":
      return null; // Too noisy, skip
    case "rate_limit":
      return null; // Skip unless it's a problem
    default:
      return null;
  }
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

        if (batch.length === 1) {
          result.push({ id: `st-${batch[0].id}`, type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const label = cat === "read"
            ? `Read ${batch.length} files`
            : cat === "glob"
              ? `Searched ${batch.length} patterns`
              : cat === "grep"
                ? `Grep ${batch.length} searches`
                : `${batch.length} ${cat} calls`;
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ id: `tg-${batch[0].id}`, type: "tool_group", category: cat, label, tools: batch, ts: batch[0].ts, totalDuration });
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
          result.push({ id: `st-${batch[0].id}`, type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ id: `eg-${batch[0].id}`, type: "edit_group", tools: batch, ts: batch[0].ts, totalDuration });
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
          result.push({ id: `st-${batch[0].id}`, type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ id: `bg-${batch[0].id}`, type: "bash_group", tools: batch, ts: batch[0].ts, totalDuration });
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
          result.push({ id: `st-${batch[0].id}`, type: "single_tool", tool: batch[0], ts: batch[0].ts });
        } else {
          const totalDuration = batch.reduce((sum, t) => sum + (t.duration_ms || 0), 0);
          result.push({ id: `pg-${batch[0].id}`, type: "playwright_group", tools: batch, ts: batch[0].ts, totalDuration });
        }
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
  /** Extract command strings from bash tools or groups. */
  if (gev.type === "single_tool") {
    return [(gev.tool.input_data?.command as string) || ""];
  }
  if (gev.type === "bash_group") {
    return gev.tools.map((t) => (t.input_data?.command as string) || "");
  }
  return [];
}

/* ── Helpers for rendering ── */

export function extractReadFiles(tools: ToolCall[]): string[] {
  return tools.map(tc => {
    const fp = extractFilePath(tc);
    return fp.split("/").pop() || fp;
  });
}

export function extractReadPaths(tools: ToolCall[]): string[] {
  return tools.map(tc => extractFilePath(tc));
}

export function extractEditSummary(tools: ToolCall[]): Array<{ file: string; path: string; added: number; removed: number }> {
  return tools.map(tc => {
    const path = extractFilePath(tc);
    const file = path.split("/").pop() || path;
    const patch = tc.output_data?.structuredPatch as Array<Record<string, unknown>> | undefined;
    let added = 0, removed = 0;
    if (patch) {
      for (const hunk of patch) {
        const lines = (hunk.lines as string[]) || [];
        for (const l of lines) {
          if (l.startsWith("+") && !l.startsWith("+++")) added++;
          if (l.startsWith("-") && !l.startsWith("---")) removed++;
        }
      }
    }
    return { file, path, added, removed };
  });
}

export function extractBashCommands(tools: ToolCall[]): Array<{ cmd: string; desc: string; output: string; exitOk: boolean; duration: number }> {
  return tools.map(tc => {
    const input = tc.input_data || {};
    const output = tc.output_data || {};
    const cmd = (input.command as string) || "";
    const desc = (input.description as string) || "";
    const stdout = (output.stdout as string) || "";
    const stderr = (output.stderr as string) || "";
    return {
      cmd: desc || cmd.slice(0, 120),
      desc,
      output: stderr ? `[stderr] ${stderr}\n${stdout}` : stdout,
      exitOk: !stderr,
      duration: tc.duration_ms || 0,
    };
  });
}
