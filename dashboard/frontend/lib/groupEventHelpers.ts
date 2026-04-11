import type { GroupedEvent } from "@/lib/groupEvents";
import type { ToolCall } from "@/lib/types";

/* ── File path extraction ── */

function extractFilePath(tc: ToolCall): string {
  const input = tc.input_data || {};
  const output = tc.output_data || {};
  const fp = (input.file_path as string) || (output.filePath as string) || "";
  return fp.replace(/^\/home\/agentuser\/repo\//, "").replace(/^\/workspace\//, "");
}

export function extractReadFiles(tools: ToolCall[]): string[] {
  return tools.map(tc => {
    const fp = extractFilePath(tc);
    return fp.split("/").pop() || fp;
  });
}

export function extractReadPaths(tools: ToolCall[]): string[] {
  return tools.map(tc => extractFilePath(tc));
}

export function extractEditSummary(tools: ToolCall[]): Array<{ id: number; file: string; path: string; added: number; removed: number }> {
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
    return { id: tc.id, file, path, added, removed };
  });
}

export function extractBashCommands(tools: ToolCall[]): Array<{ id: number; cmd: string; desc: string; output: string; exitOk: boolean; duration: number }> {
  return tools.map(tc => {
    const input = tc.input_data || {};
    const output = tc.output_data || {};
    const cmd = (input.command as string) || "";
    const desc = (input.description as string) || "";
    const stdout = (output.stdout as string) || "";
    const stderr = (output.stderr as string) || "";
    return {
      id: tc.id,
      cmd: desc || cmd.slice(0, 120),
      desc,
      output: stderr ? `[stderr] ${stderr}\n${stdout}` : stdout,
      exitOk: !stderr,
      duration: tc.duration_ms || 0,
    };
  });
}

/* ── Commit divider detection ── */

export const ROUND_PATTERN = /\[Round\s+(\d+)\]/i;

export function insertCommitDividers(groups: GroupedEvent[]): GroupedEvent[] {
  const out: GroupedEvent[] = [];
  for (const gev of groups) {
    out.push(gev);
    const commitRound = detectGitCommit(gev);
    if (commitRound !== null) {
      const roundLabel = commitRound > 0 ? `Round ${commitRound}` : "Round";
      const label = `${roundLabel} complete`;
      out.push({ id: `div-${gev.ts}-${label}`, type: "divider", label, ts: gev.ts });
    }
  }
  return out;
}

function detectGitCommit(gev: GroupedEvent): number | null {
  const commands = extractCommands(gev);
  for (const cmd of commands) {
    if (!cmd.includes("git commit") && !cmd.includes("git -c")) continue;
    if (!cmd.includes("commit")) continue;
    const match = cmd.match(ROUND_PATTERN);
    if (match) return parseInt(match[1], 10);
    return 0;
  }
  return null;
}

function extractCommands(gev: GroupedEvent): string[] {
  if (gev.type === "single_tool") {
    return [(gev.tool.input_data?.command as string) || ""];
  }
  if (gev.type === "bash_group") {
    return gev.tools.map((t) => (t.input_data?.command as string) || "");
  }
  return [];
}
