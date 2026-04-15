export interface DiffLine {
  type: "add" | "remove" | "context" | "hunk-header" | "meta";
  content: string;
  oldLine: number | null;
  newLine: number | null;
}

const HUNK_HEADER_RE = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;

export function parseDiffLines(patch: string): DiffLine[] {
  const lines = patch.split("\n");
  const result: DiffLine[] = [];
  let oldLine = 0;
  let newLine = 0;

  for (const raw of lines) {
    if (raw.startsWith("@@")) {
      const m = HUNK_HEADER_RE.exec(raw);
      if (m) {
        oldLine = parseInt(m[1], 10);
        newLine = parseInt(m[2], 10);
      }
      result.push({ type: "hunk-header", content: raw, oldLine: null, newLine: null });
      continue;
    }

    if (
      raw.startsWith("--- ") ||
      raw.startsWith("+++ ") ||
      raw.startsWith("diff --git") ||
      raw.startsWith("index ") ||
      raw.startsWith("rename from") ||
      raw.startsWith("rename to") ||
      raw.startsWith("new file mode") ||
      raw.startsWith("deleted file mode")
    ) {
      result.push({ type: "meta", content: raw, oldLine: null, newLine: null });
      continue;
    }

    if (raw.startsWith("+")) {
      result.push({ type: "add", content: raw.slice(1), oldLine: null, newLine: newLine });
      newLine++;
      continue;
    }

    if (raw.startsWith("-")) {
      result.push({ type: "remove", content: raw.slice(1), oldLine: oldLine, newLine: null });
      oldLine++;
      continue;
    }

    // context line (space or other)
    result.push({ type: "context", content: raw.startsWith(" ") ? raw.slice(1) : raw, oldLine: oldLine, newLine: newLine });
    oldLine++;
    newLine++;
  }

  return result;
}

const EXT_TO_LANG: Record<string, string> = {
  py: "python",
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  md: "markdown",
  css: "css",
  json: "json",
  html: "html",
  sql: "sql",
  sh: "bash",
  bash: "bash",
  yaml: "yaml",
  yml: "yaml",
  go: "go",
  rs: "rust",
};

export function langFromPath(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase() ?? "";
  return EXT_TO_LANG[ext] ?? "text";
}
