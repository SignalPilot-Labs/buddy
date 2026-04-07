import type { FileChange } from "@/lib/types";
import type { DiffFile } from "@/lib/api";

export interface TreeNode {
  name: string;
  fullPath: string;
  isDir: boolean;
  children: Map<string, TreeNode>;
  added: number;
  removed: number;
  status?: string;
}

export function norm(p: string): string {
  return p
    .replace(/^\/home\/agentuser\/repo\//, "")
    .replace(/^\/workspace\//, "")
    .replace(/^\/home\/agentuser\//, "~/");
}

export function buildTreeFromDiff(files: DiffFile[]): TreeNode {
  const root: TreeNode = { name: "", fullPath: "", isDir: true, children: new Map(), added: 0, removed: 0 };
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

export function buildTreeFromChanges(changes: FileChange[]): TreeNode {
  const root: TreeNode = { name: "", fullPath: "", isDir: true, children: new Map(), added: 0, removed: 0 };
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
