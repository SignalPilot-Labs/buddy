import type { FeedEvent, ToolCall } from "./types";
import type { GroupedEvent } from "./groupEventTypes";

export function extractFilePath(tc: ToolCall): string {
  const input = tc.input_data || {};
  const output = tc.output_data || {};
  const fp = (input.file_path as string) || (output.filePath as string) || "";
  return fp
    .replace(/^\/home\/agentuser\/repo\//, "")
    .replace(/^\/workspace\//, "");
}

export function extractReadFiles(tools: ToolCall[]): string[] {
  return tools.map((tc) => {
    const fp = extractFilePath(tc);
    return fp.split("/").pop() || fp;
  });
}

export function extractReadPaths(tools: ToolCall[]): string[] {
  return tools.map((tc) => extractFilePath(tc));
}

export function extractEditSummary(
  tools: ToolCall[],
): Array<{ file: string; path: string; added: number; removed: number }> {
  return tools.map((tc) => {
    const path = extractFilePath(tc);
    const file = path.split("/").pop() || path;
    const patch = tc.output_data?.structuredPatch as
      | Array<Record<string, unknown>>
      | undefined;
    let added = 0,
      removed = 0;
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

export function extractBashCommands(tools: ToolCall[]): Array<{
  cmd: string;
  desc: string;
  output: string;
  exitOk: boolean;
  duration: number;
}> {
  return tools.map((tc) => {
    const input = tc.input_data || {};
    const output = tc.output_data || {};
    const cmd = (input.command as string) || "";
    const desc = (input.description as string) || "";
    const stdout = (output.stdout as string) || "";
    const stderr = (output.stderr as string) || "";
    return {
      cmd: cmd || desc,
      desc,
      output: stderr ? `[stderr] ${stderr}\n${stdout}` : stdout,
      exitOk: !stderr,
      duration: tc.duration_ms || 0,
    };
  });
}

export function milestoneFromAudit(event: FeedEvent): GroupedEvent | null {
  if (event._kind !== "audit") return null;
  const d = event.data.details;
  const ts = event.data.ts;

  switch (event.data.event_type) {
    case "run_starting":
      return {
        id: `ms-${ts}-Run Starting`,
        type: "milestone",
        label: "Run Starting",
        detail: String(d.repo || ""),
        color: "#ffaa00",
        ts,
        event,
      };
    case "sandbox_created":
      return {
        id: `ms-${ts}-Sandbox Created`,
        type: "milestone",
        label: "Sandbox Created",
        detail: "",
        color: "#88ccff",
        ts,
        event,
      };
    case "repo_cloned":
      return {
        id: `ms-${ts}-Repo Cloned`,
        type: "milestone",
        label: "Repo Cloned",
        detail: String(d.repo || ""),
        color: "#88ccff",
        ts,
        event,
      };
    case "run_started":
      return {
        id: `ms-${ts}-Run Started`,
        type: "milestone",
        label: "Run Started",
        detail: "",
        color: "#88ccff",
        ts,
        event,
      };
    case "round_ended": {
      const roundNum = d.round_number as number | undefined;
      const label = roundNum ? `Round ${roundNum} complete` : "Round complete";
      return { id: `div-${ts}-${label}`, type: "divider", label, ts };
    }
    case "pr_created":
      return {
        id: `ms-${ts}-PR Created`,
        type: "milestone",
        label: "PR Created",
        detail: String(d.url || ""),
        color: "#00ff88",
        ts,
        event,
      };
    case "pr_failed":
      return {
        id: `ctrl-${ts}-pr-failed`,
        type: "control",
        text: `PR failed: ${String(d.error || "Unknown error")}`,
        details: d,
        ts,
      };
    case "killed":
      return {
        id: `ms-${ts}-Killed`,
        type: "milestone",
        label: "Killed",
        detail: `after ${(d.elapsed_minutes as number)?.toFixed(1) || "?"}min`,
        color: "#ff4444",
        ts,
        event,
      };
    case "fatal_error":
      return {
        id: `ctrl-${ts}-fatal`,
        type: "control",
        text: String(d.error || "Unknown error"),
        details: d,
        ts,
      };
    case "end_session_denied":
      return {
        id: `ms-${ts}-End Run Denied`,
        type: "milestone",
        label: "End Run Denied",
        detail: `${d.remaining_minutes || "?"}m remaining`,
        color: "#ffaa00",
        ts,
        event,
      };
    case "run_unlocked":
      return {
        id: `ms-${ts}-Run Unlocked`,
        type: "milestone",
        label: "Run Unlocked",
        detail: "",
        color: "#00ff88",
        ts,
        event,
      };
    case "stop_requested":
      return {
        id: `ms-${ts}-Stop Requested`,
        type: "milestone",
        label: "Stop Requested",
        detail: String(d.reason || ""),
        color: "#ff8844",
        ts,
        event,
      };
    case "pause_requested":
      return {
        id: `ms-${ts}-Pause Requested`,
        type: "milestone",
        label: "Pause Requested",
        detail: "",
        color: "#ffaa00",
        ts,
        event,
      };
    case "rate_limit": {
      const resetEpoch = d.resets_at as number | undefined;
      let resetText = "Rate limited";
      if (resetEpoch) {
        const resetDate = new Date(resetEpoch * 1000);
        const diffMs = resetEpoch * 1000 - Date.now();
        const timeStr = resetDate.toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        });
        if (diffMs <= 0) {
          resetText = `Rate limited — resets ${timeStr} (ready)`;
        } else {
          const h = Math.floor(diffMs / 3600000);
          const m = Math.floor((diffMs % 3600000) / 60000);
          resetText =
            h > 0
              ? `Rate limited — resets ${timeStr} (${h}h ${m}m)`
              : `Rate limited — resets ${timeStr} (${m}m)`;
        }
      }
      return {
        id: `ctrl-${ts}-rate-limit`,
        type: "control",
        text: resetText,
        details: d,
        ts,
      };
    }
    case "prompt_injected":
      return {
        id: `up-${event.data.id}-${ts}`,
        type: "user_prompt",
        prompt: String(d.prompt || ""),
        ts,
        pending: Boolean(d._pending),
        failed: Boolean(d._failed),
        injected: true,
      };
    case "prompt_submitted":
      return {
        id: `up-${event.data.id}-${ts}`,
        type: "user_prompt",
        prompt: String(d.prompt || ""),
        ts,
        pending: Boolean(d._pending),
        failed: Boolean(d._failed),
      };
    case "run_resumed":
      return {
        id: `ms-${ts}-Session Resumed`,
        type: "milestone",
        label: "Run Resumed",
        detail: "",
        color: "#00ff88",
        ts,
        event,
      };
    case "auto_commit":
      return {
        id: `ms-${ts}-Auto Commit`,
        type: "milestone",
        label: "Auto Commit",
        detail: String(d.reason || "").slice(0, 100),
        color: "#888888",
        ts,
        event,
      };
    case "no_changes":
      return {
        id: `ms-${ts}-No Changes`,
        type: "milestone",
        label: "No Changes",
        detail: String(d.base_branch || ""),
        color: "#888888",
        ts,
        event,
      };
    case "push_failed":
      return {
        id: `ctrl-${ts}-push-failed`,
        type: "control",
        text: `Push failed: ${String(d.error || "Unknown error")}`,
        details: d,
        ts,
      };
    case "sandbox_crash":
      return {
        id: `ctrl-${ts}-sandbox-crash`,
        type: "control",
        text: `Sandbox crashed: ${String(d.error || "Unknown error")}`,
        details: d,
        ts,
      };
    case "agent_restarted":
      return {
        id: `ctrl-${ts}-agent-restarted`,
        type: "control",
        text: `Agent restarted: ${String(d.error || "Container restarted while run was in progress")}`,
        details: d,
        ts,
      };
    case "permission_denied":
      return {
        id: `ms-${ts}-Permission Denied`,
        type: "milestone",
        label: "Permission Denied",
        detail: String(d.tool_name || ""),
        color: "#ff4444",
        ts,
        event,
      };
    case "run_ended": {
      const elapsed = d.elapsed_minutes as number | undefined;
      const detail = elapsed ? `${elapsed}min` : "";
      return {
        id: `ms-${ts}-Run Ended`,
        type: "milestone",
        label: "Run Ended",
        detail,
        color: "#88ccff",
        ts,
        event,
      };
    }
    case "mcp_warning":
      return {
        id: `ctrl-${ts}-mcp-warning`,
        type: "control",
        text: `MCP warning: ${String(d.message || "Unknown MCP issue")}`,
        details: d,
        ts,
      };
    case "sandbox_queued":
      return {
        id: `ms-${ts}-Sandbox Queued`,
        type: "milestone",
        label: "Sandbox Queued",
        detail: d.backend_id ? `Job ${String(d.backend_id)}` : "",
        color: "#88ccff",
        ts,
        event,
      };
    case "sandbox_start_failed":
      return {
        id: `ctrl-${ts}-sandbox-start-failed`,
        type: "control",
        text: `Sandbox start failed: ${String(d.error || "Unknown error")}`,
        details: d,
        ts,
      };
    default:
      return null;
  }
}
