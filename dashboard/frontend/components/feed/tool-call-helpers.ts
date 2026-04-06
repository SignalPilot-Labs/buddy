import type { ToolCall } from "@/lib/types";
import { getToolCategory } from "@/lib/types";

export type ToolSummaryStrings = {
  todoSummary: { done: string; active: string; pending: string };
  playwright: { screenshot: string; click: string; formInput: string; evaluate: string; domSnapshot: string };
};

export type OutputSummaryStrings = {
  noOutput: string;
  nLines: string;
  nLinesWritten: string;
};

export function extractToolSummary(tc: ToolCall, strings: ToolSummaryStrings): string {
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
    case "glob":
      return (input.pattern as string) || "";
    case "grep": {
      const pat = (input.pattern as string) || "";
      const path = (input.path as string) || "";
      const shortPath = path.split("/").slice(-2).join("/");
      return `/${pat}/ in ${shortPath}`;
    }
    case "agent":
      return (input.description as string) || "";
    case "web_search":
      return (input.query as string) || "";
    case "web_fetch":
      return (input.url as string) || "";
    case "todo": {
      const todos = (input.todos as Array<{ status: string; content: string }>) || [];
      const active = todos.filter((item) => item.status === "in_progress");
      const pending = todos.filter((item) => item.status === "pending");
      const done = todos.filter((item) => item.status === "completed");
      return `${done.length} ${strings.todoSummary.done}, ${active.length} ${strings.todoSummary.active}, ${pending.length} ${strings.todoSummary.pending}`;
    }
    case "tool_search":
      return (input.query as string) || "";
    case "skill":
      return (input.skill as string) || "";
    case "playwright_navigate":
      return (input.url as string) || "";
    case "playwright_screenshot":
      return (input.filename as string) || strings.playwright.screenshot;
    case "playwright_click":
      return strings.playwright.click;
    case "playwright_form":
    case "playwright_type":
      return strings.playwright.formInput;
    case "playwright_evaluate":
      return strings.playwright.evaluate;
    case "playwright_snapshot":
      return strings.playwright.domSnapshot;
    case "session_gate":
      return "end_session";
    default:
      return JSON.stringify(input).slice(0, 80);
  }
}

export function extractOutputSummary(tc: ToolCall, strings: OutputSummaryStrings): string | null {
  const output = tc.output_data;
  if (!output) return null;
  const cat = getToolCategory(tc.tool_name);

  switch (cat) {
    case "bash": {
      const stdout = (output.stdout as string) || "";
      const stderr = (output.stderr as string) || "";
      const text = stdout || stderr;
      if (!text) return strings.noOutput;
      const lines = text.split("\n").filter(Boolean);
      if (lines.length <= 3) return text.trim();
      return `${lines.length} ${strings.nLines}`;
    }
    case "read": {
      const file = output.file as Record<string, unknown> | undefined;
      if (file) return `${file.totalLines || "?"} ${strings.nLines}`;
      return null;
    }
    case "edit": {
      const patch = output.structuredPatch as Array<Record<string, unknown>> | undefined;
      if (patch && patch.length > 0) {
        let added = 0;
        let removed = 0;
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
        return `${added} ${strings.nLinesWritten}`;
      }
      return (output.type as string) || null;
    }
    default:
      return null;
  }
}
