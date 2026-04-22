export function fmtTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("en-US", {
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
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
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

export const IDLE_WARN_MS = 300_000;
