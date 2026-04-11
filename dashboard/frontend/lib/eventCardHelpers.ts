import type { ToolCall } from "@/lib/types";
import { getToolCategory } from "@/lib/types";
import { MS_PER_SECOND, MS_PER_MINUTE, MS_PER_HOUR } from "@/lib/constants";

export const UNKNOWN_TIME_LABEL = "unknown";

export function fmtTime(ts: string): string {
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

export function fmtDuration(ms: number): string {
  if (ms < MS_PER_SECOND) return `${ms}ms`;
  if (ms < MS_PER_MINUTE) return `${(ms / MS_PER_SECOND).toFixed(1)}s`;
  return `${(ms / MS_PER_MINUTE).toFixed(1)}m`;
}

/**
 * Format a millisecond duration as "Xh Ym" or "Ym".
 * Used wherever a coarse hours+minutes breakdown is needed (AuditCard, groupEvents).
 */
export function formatHoursMinutes(diffMs: number): string {
  const h = Math.floor(diffMs / MS_PER_HOUR);
  const m = Math.floor((diffMs % MS_PER_HOUR) / MS_PER_MINUTE);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

// Sandbox containers run all tool calls with cwd under /home/agentuser/.
// Stripping that prefix turns `/home/agentuser/repo/pyproject.toml` into
// `repo/pyproject.toml` (which is what users actually want to see), while
// preserving absolute paths like `/tmp/round-1/architect.md` in full so
// round-output files don't get confused with repo files.
const SANDBOX_CWD_PREFIX = "/home/agentuser/";

export function shortPath(p: string): string {
  if (p.startsWith(SANDBOX_CWD_PREFIX)) {
    return p.slice(SANDBOX_CWD_PREFIX.length);
  }
  return p;
}

export function extractResultText(data: Record<string, unknown>): string {
  if ("result" in data && typeof data.result === "string") return data.result;
  if ("_raw" in data && typeof data._raw === "string") return data._raw;
  const content = data.content;
  if (Array.isArray(content)) {
    const texts = content
      .filter(
        (b: unknown) =>
          typeof b === "object" &&
          b !== null &&
          (b as Record<string, unknown>).type === "text"
      )
      .map((b: unknown) =>
        String((b as Record<string, unknown>).text || "")
      );
    if (texts.length > 0) return texts.join("\n");
  }
  return "";
}

export function extractToolSummary(tc: ToolCall): string {
  const input = tc.input_data;
  if (!input) return "";
  const cat = getToolCategory(tc.tool_name);

  switch (cat) {
    case "bash": {
      const cmd = (input.command as string) || "";
      const desc = (input.description as string) || "";
      return desc || (cmd.length > 100 ? cmd.slice(0, 100) + "…" : cmd);
    }
    case "read": {
      const fp = (input.file_path as string) || "";
      const name = fp.split("/").pop() || fp;
      const offset = input.offset ? ` :${input.offset}` : "";
      return `${name}${offset}`;
    }
    case "write": {
      const fp = (input.file_path as string) || "";
      return fp.split("/").pop() || fp;
    }
    case "edit": {
      const fp = (input.file_path as string) || "";
      return fp.split("/").pop() || fp;
    }
    case "glob": return (input.pattern as string) || "";
    case "grep": {
      const pat = (input.pattern as string) || "";
      const path = (input.path as string) || "";
      return `/${pat}/ in ${shortPath(path)}`;
    }
    case "agent": return (input.description as string) || "";
    case "web_search": return (input.query as string) || "";
    case "web_fetch": return (input.url as string) || "";
    case "todo": {
      const todos = (input.todos as Array<{ status: string; content: string }>) || [];
      const active = todos.filter(t => t.status === "in_progress");
      const pending = todos.filter(t => t.status === "pending");
      const done = todos.filter(t => t.status === "completed");
      return `${done.length} done, ${active.length} active, ${pending.length} pending`;
    }
    case "tool_search": return (input.query as string) || "";
    case "skill": return (input.skill as string) || "";
    case "playwright_navigate": return (input.url as string) || "";
    case "playwright_screenshot": return (input.filename as string) || "screenshot";
    case "playwright_click": return "click";
    case "playwright_form": case "playwright_type": return "form input";
    case "playwright_evaluate": return "evaluate";
    case "playwright_snapshot": return "DOM snapshot";
    case "session_gate": return "end_session";
    default: return JSON.stringify(input).slice(0, 80);
  }
}

export function extractOutputSummary(tc: ToolCall): string | null {
  const output = tc.output_data;
  if (!output) return null;
  const cat = getToolCategory(tc.tool_name);

  switch (cat) {
    case "bash": {
      const stdout = (output.stdout as string) || "";
      const stderr = (output.stderr as string) || "";
      const text = stdout || stderr;
      if (!text) return "(no output)";
      const lines = text.split("\n").filter(Boolean);
      if (lines.length <= 3) return text.trim();
      return `${lines.length} lines`;
    }
    case "read": {
      const file = output.file as Record<string, unknown> | undefined;
      if (file) return `${file.totalLines || "?"} lines`;
      return null;
    }
    case "edit": {
      const patch = output.structuredPatch as Array<Record<string, unknown>> | undefined;
      if (patch && patch.length > 0) {
        let added = 0, removed = 0;
        for (const hunk of patch) {
          const lines = (hunk.lines as string[]) || [];
          for (const l of lines) {
            if (l.startsWith("+") && !l.startsWith("+++")) added++;
            if (l.startsWith("-") && !l.startsWith("---")) removed++;
          }
        }
        return `+${added} -${removed}`;
      }
      return null;
    }
    case "write": {
      const patch = output.structuredPatch as Array<Record<string, unknown>> | undefined;
      if (patch) {
        let added = 0;
        for (const hunk of patch) {
          added += (hunk.newLines as number) || 0;
        }
        return `${added} lines written`;
      }
      return (output.type as string) || null;
    }
    default: return null;
  }
}

export const IDLE_WARN_MS = 60_000;
