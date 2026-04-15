import type { FeedEvent, FileChange } from "@/lib/types";
import type { DiffFile } from "@/lib/api";
import { getToolCategory } from "@/lib/types";

/* ── Patch types ── */
interface PatchHunk {
  lines?: string[];
}

/* ── Shared patch line counter ── */
function _countPatchLines(hunks: PatchHunk[]): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const hunk of hunks) {
    if (hunk.lines === undefined) continue;
    for (const line of hunk.lines) {
      if (line.startsWith("+") && !line.startsWith("+++")) added++;
      if (line.startsWith("-") && !line.startsWith("---")) removed++;
    }
  }
  return { added, removed };
}

/* ── Tree Node ── */
export interface TreeNode {
  name: string;
  fullPath: string;
  isDir: boolean;
  children: Map<string, TreeNode>;
  added: number;
  removed: number;
  status?: string;
}

/* ── Path normalisation ── */
export function norm(p: string): string {
  return p
    .replace(/^\/home\/agentuser\/repo\//, "")
    .replace(/^\/workspace\//, "")
    .replace(/^\/home\/agentuser\//, "~/");
}

/* ── Extract file changes from tool call events (live feed) ── */
export function extractFileChanges(events: FeedEvent[]): FileChange[] {
  const changes: FileChange[] = [];
  for (const ev of events) {
    if (ev._kind !== "tool") continue;
    const tc = ev.data;
    const cat = getToolCategory(tc.tool_name);
    const input = tc.input_data || {};
    const output = tc.output_data || {};

    switch (cat) {
      case "read": {
        const fileObj = (output as Record<string, unknown>)?.file as Record<string, unknown> | undefined;
        const fp = (input.file_path as string) || (fileObj?.filePath as string) || "";
        if (fp) {
          changes.push({
            path: norm(fp),
            action: "read",
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
      case "write": {
        const fp = (input.file_path as string) || (output.filePath as string) || "";
        if (fp) {
          const patch = output.structuredPatch as PatchHunk[] | undefined;
          const counts = patch ? _countPatchLines(patch) : undefined;
          changes.push({
            path: norm(fp),
            action: "write",
            linesAdded: counts ? counts.added || undefined : undefined,
            linesRemoved: counts ? counts.removed || undefined : undefined,
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
      case "edit": {
        const fp = (input.file_path as string) || (output.filePath as string) || "";
        if (fp) {
          const patch = output.structuredPatch as PatchHunk[] | undefined;
          const counts = patch ? _countPatchLines(patch) : undefined;
          changes.push({
            path: norm(fp),
            action: "edit",
            linesAdded: counts ? counts.added || undefined : undefined,
            linesRemoved: counts ? counts.removed || undefined : undefined,
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
    }
  }
  return changes;
}

/* ── Build tree from git diff files ── */
export function buildTreeFromDiff(files: DiffFile[]): TreeNode {
  const root: TreeNode = {
    name: "",
    fullPath: "",
    isDir: true,
    children: new Map(),
    added: 0,
    removed: 0,
  };
  for (const f of files) {
    const parts = f.path.split("/").filter(Boolean);
    let cur = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      if (!cur.children.has(part)) {
        cur.children.set(part, {
          name: part,
          fullPath: parts.slice(0, i + 1).join("/"),
          isDir: !isLast,
          children: new Map(),
          added: 0,
          removed: 0,
        });
      }
      cur = cur.children.get(part)!;
      if (isLast) {
        cur.added = f.added;
        cur.removed = f.removed;
        cur.status = f.status;
      }
    }
  }
  return root;
}

/* ── Build tree from live event-stream changes ── */
export function buildTreeFromChanges(changes: FileChange[]): TreeNode {
  const root: TreeNode = {
    name: "",
    fullPath: "",
    isDir: true,
    children: new Map(),
    added: 0,
    removed: 0,
  };
  const seen = new Map<string, { added: number; removed: number }>();
  for (const c of changes) {
    if (c.action === "read") continue;
    const key = c.path;
    const existing = seen.get(key) || { added: 0, removed: 0 };
    existing.added += c.linesAdded || 0;
    existing.removed += c.linesRemoved || 0;
    seen.set(key, existing);
  }
  for (const [path, stats] of seen) {
    const parts = path.split("/").filter(Boolean);
    let cur = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      if (!cur.children.has(part)) {
        cur.children.set(part, {
          name: part,
          fullPath: parts.slice(0, i + 1).join("/"),
          isDir: !isLast,
          children: new Map(),
          added: 0,
          removed: 0,
        });
      }
      cur = cur.children.get(part)!;
      if (isLast) {
        cur.added = stats.added;
        cur.removed = stats.removed;
        cur.status = "modified";
      }
    }
  }
  return root;
}

/* ── Merge two trees — session wins on path conflict ── */
export function mergeTrees(git: TreeNode, session: TreeNode): TreeNode {
  return _mergeDir(git, session);
}

function _mergeDir(git: TreeNode, session: TreeNode): TreeNode {
  // If session has no children in this dir, just use git as-is (no clone)
  if (session.children.size === 0) return git;
  // If git has no children, just use session as-is
  if (git.children.size === 0) return session;

  const children = new Map<string, TreeNode>();

  // Git entries — shared by reference unless session conflicts
  for (const [key, node] of git.children) {
    if (!session.children.has(key)) {
      children.set(key, node); // share reference, no clone
    }
  }

  // Session entries — shared by reference, or merged if both are dirs
  for (const [key, sNode] of session.children) {
    const gitNode = git.children.get(key);
    if (!gitNode) {
      children.set(key, sNode);
    } else if (gitNode.isDir && sNode.isDir) {
      children.set(key, _mergeDir(gitNode, sNode));
    } else {
      children.set(key, sNode); // session wins
    }
  }

  return { ...git, children };
}
