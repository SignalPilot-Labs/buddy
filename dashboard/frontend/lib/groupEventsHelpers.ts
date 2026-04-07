import type { FeedEvent, GroupedEvent, ToolCall } from "@/lib/types";

/* ── milestoneFromAudit ── */

export function milestoneFromAudit(event: FeedEvent): GroupedEvent | null {
  if (event._kind !== "audit") return null;
  const d = event.data.details;
  const ts = event.data.ts;

  switch (event.data.event_type) {
    case "run_started":
      return { type: "milestone", label: "Run Started", detail: `${d.model || "claude"} · ${d.branch || ""}`, color: "#88ccff", ts, event };
    case "round_complete":
      return { type: "divider", label: `Round ${d.round} complete · ${(d.cost_usd as number)?.toFixed(3) || "?"} USD · ${d.turns} turns`, ts };
    case "pr_created":
      return { type: "milestone", label: "PR Created", detail: String(d.url || ""), color: "#00ff88", ts, event };
    case "pr_failed":
      return { type: "milestone", label: "PR Failed", detail: String(d.error || "").slice(0, 100), color: "#ff4444", ts, event };
    case "session_ended":
      return { type: "milestone", label: "Session Ended", detail: `${d.changes_made || 0} changes · ${(d.elapsed_minutes as number)?.toFixed(1) || "?"}min`, color: "#88ccff", ts, event };
    case "killed":
      return { type: "milestone", label: "Killed", detail: `after ${(d.elapsed_minutes as number)?.toFixed(1) || "?"}min`, color: "#ff4444", ts, event };
    case "fatal_error":
      return { type: "milestone", label: "Fatal Error", detail: String(d.error || "").slice(0, 100), color: "#ff4444", ts, event };
    case "planner_invoked":
      return { type: "milestone", label: "Planner Invoked", detail: `Round ${d.round} · ${d.tool_summary || ""}`, color: "#ff8844", ts, event };
    case "end_session_denied":
      return { type: "milestone", label: "Session Denied", detail: `${d.time_remaining || "?"} remaining`, color: "#ffaa00", ts, event };
    case "session_unlocked":
      return { type: "milestone", label: "Session Unlocked", detail: "", color: "#00ff88", ts, event };
    case "stop_requested":
      return { type: "milestone", label: "Stop Requested", detail: String(d.reason || ""), color: "#ff8844", ts, event };
    case "rate_limit_paused":
      return { type: "milestone", label: "Rate Limited", detail: `wait ${d.wait_seconds || "?"}s`, color: "#ffaa00", ts, event };
    case "prompt_injected":
      return { type: "user_prompt", prompt: String(d.prompt || ""), ts };
    case "session_resumed":
      return { type: "milestone", label: "Session Resumed", detail: `branch ${String(d.branch || "").slice(0, 40)}`, color: "#00ff88", ts, event };
    case "auto_commit":
      return { type: "milestone", label: "Auto Commit", detail: String(d.reason || "").slice(0, 100), color: "#888888", ts, event };
    case "push_failed":
      return { type: "milestone", label: "Push Failed", detail: String(d.error || "").slice(0, 100), color: "#ff4444", ts, event };
    case "permission_denied":
      return { type: "milestone", label: "Permission Denied", detail: String(d.tool_name || ""), color: "#ff4444", ts, event };
    case "run_ended":
      return { type: "milestone", label: "Run Ended", detail: String(d.status || ""), color: "#88ccff", ts, event };
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

/* ── File path extraction helper ── */

function extractFilePath(tc: ToolCall): string {
  const input = tc.input_data || {};
  const output = tc.output_data || {};
  const fp = (input.file_path as string) || (output.filePath as string) || "";
  return fp.replace(/^\/home\/agentuser\/repo\//, "").replace(/^\/workspace\//, "");
}

/* ── Rendering helpers ── */

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
