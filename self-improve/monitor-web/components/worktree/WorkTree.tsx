"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import type { FeedEvent, FileChange } from "@/lib/types";
import { getToolCategory } from "@/lib/types";

/* ── Extract file changes from tool call events ── */
function extractFileChanges(events: FeedEvent[]): FileChange[] {
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
            path: normalizePath(fp),
            action: "read",
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
      case "write": {
        const fp = (input.file_path as string) || (output.filePath as string);
        if (fp) {
          const patch = output.structuredPatch as Array<Record<string, unknown>> | undefined;
          let added = 0;
          if (patch) {
            for (const hunk of patch) {
              added += (hunk.newLines as number) || 0;
            }
          }
          changes.push({
            path: normalizePath(fp),
            action: "write",
            linesAdded: added || undefined,
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
      case "edit": {
        const fp = (input.file_path as string) || (output.filePath as string);
        if (fp) {
          const patch = output.structuredPatch as Array<Record<string, unknown>> | undefined;
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
          changes.push({
            path: normalizePath(fp),
            action: "edit",
            linesAdded: added || undefined,
            linesRemoved: removed || undefined,
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
      case "bash": {
        const cmd = (input.command as string) || "";
        if (cmd.includes("git commit") || cmd.includes("git add")) {
          changes.push({
            path: "git",
            action: "exec",
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: "git",
          });
        }
        break;
      }
      case "glob": {
        const pattern = (input.pattern as string) || "";
        if (pattern) {
          changes.push({
            path: normalizePath(pattern),
            action: "search",
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

function normalizePath(p: string): string {
  // Strip common prefixes
  return p
    .replace(/^\/home\/agentuser\/repo\//, "")
    .replace(/^\/workspace\//, "")
    .replace(/^\/home\/agentuser\//, "~/");
}

/* ── Build file tree from changes ── */
interface TreeNode {
  name: string;
  fullPath: string;
  type: "file" | "dir";
  children: Map<string, TreeNode>;
  changes: FileChange[];
}

function buildTree(changes: FileChange[]): TreeNode {
  const root: TreeNode = { name: "", fullPath: "", type: "dir", children: new Map(), changes: [] };

  for (const change of changes) {
    if (change.path === "git" || change.action === "search") continue;
    const parts = change.path.split("/").filter(Boolean);
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;

      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          fullPath: parts.slice(0, i + 1).join("/"),
          type: isLast ? "file" : "dir",
          children: new Map(),
          changes: [],
        });
      }
      current = current.children.get(part)!;
      if (isLast) {
        current.changes.push(change);
      }
    }
  }

  return root;
}

/* ── File icon by extension ── */
function FileIcon({ name, action }: { name: string; action?: string }) {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  let color = "#555";

  if (action === "write" || action === "create") color = "#cc88ff";
  else if (action === "edit") color = "#ffcc44";
  else if (action === "read") color = "#88ccff";

  if (ext === "tsx" || ext === "ts") color = action ? color : "#3178c6";
  if (ext === "css") color = action ? color : "#264de4";
  if (ext === "py") color = action ? color : "#3776ab";
  if (ext === "json") color = action ? color : "#777";
  if (ext === "md") color = action ? color : "#555";
  if (ext === "sql") color = action ? color : "#e38c00";

  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke={color} strokeWidth="1" strokeLinecap="round">
      <path d="M3 1.5h4.5l2.5 2.5v6.5a1 1 0 01-1 1H3a1 1 0 01-1-1v-8a1 1 0 011-1z" />
      <polyline points="7.5 1.5 7.5 4 10 4" />
    </svg>
  );
}

function DirIcon({ open }: { open: boolean }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#555" strokeWidth="1" strokeLinecap="round">
      {open ? (
        <>
          <path d="M1 3.5h3l1-1h4.5a1 1 0 011 1V4H2.5L1 9V3.5z" />
          <path d="M2.5 4L1 9h8.5l1.5-5H2.5z" />
        </>
      ) : (
        <path d="M1 3h3l1 1h5a1 1 0 011 1v5a1 1 0 01-1 1H2a1 1 0 01-1-1V3z" />
      )}
    </svg>
  );
}

/* ── Tree Node Component ── */
function TreeNodeItem({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.type === "dir" && node.children.size > 0;
  const hasWriteChanges = node.changes.some(c => c.action === "write" || c.action === "edit" || c.action === "create");

  const totalAdded = node.changes.reduce((sum, c) => sum + (c.linesAdded || 0), 0);
  const totalRemoved = node.changes.reduce((sum, c) => sum + (c.linesRemoved || 0), 0);

  const sortedChildren = useMemo(() => {
    const arr = Array.from(node.children.values());
    // Dirs first, then files
    return arr.sort((a, b) => {
      if (a.type === "dir" && b.type !== "dir") return -1;
      if (a.type !== "dir" && b.type === "dir") return 1;
      return a.name.localeCompare(b.name);
    });
  }, [node.children]);

  return (
    <div>
      <div
        className={clsx(
          "flex items-center gap-1.5 py-[3px] px-1 rounded cursor-pointer transition-colors text-[10px]",
          "hover:bg-white/[0.03]",
          hasWriteChanges && "bg-[#ffcc44]/[0.02]"
        )}
        style={{ paddingLeft: depth * 14 }}
        onClick={() => isDir && setOpen(!open)}
      >
        {isDir ? (
          <span className="shrink-0">
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="#444" strokeWidth="1.5" strokeLinecap="round"
              className={clsx("transition-transform duration-150", open && "rotate-90")}>
              <polyline points="2 1 6 4 2 7" />
            </svg>
          </span>
        ) : (
          <span className="w-2 shrink-0" />
        )}

        {isDir ? <DirIcon open={open} /> : <FileIcon name={node.name} action={node.changes[0]?.action} />}

        <span className={clsx(
          "flex-1 truncate",
          hasWriteChanges ? "text-[#ccc]" : "text-[#777]"
        )}>
          {node.name}
        </span>

        {/* LOC change indicators */}
        {totalAdded > 0 && (
          <span className="text-[8px] text-[#00ff88]/60 tabular-nums shrink-0">+{totalAdded}</span>
        )}
        {totalRemoved > 0 && (
          <span className="text-[8px] text-[#ff4444]/60 tabular-nums shrink-0">-{totalRemoved}</span>
        )}
        {node.changes.length > 0 && !totalAdded && !totalRemoved && (
          <span className="text-[8px] text-[#555] tabular-nums shrink-0">
            {node.changes.length}x
          </span>
        )}
      </div>

      <AnimatePresence>
        {open && isDir && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            {sortedChildren.map((child) => (
              <TreeNodeItem key={child.fullPath} node={child} depth={depth + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Changelog ── */
function ChangeLog({ changes }: { changes: FileChange[] }) {
  // Group by file, show most recent changes
  const writeChanges = changes.filter(c => c.action === "write" || c.action === "edit" || c.action === "create");
  const sorted = [...writeChanges].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  const recent = sorted.slice(0, 20);

  if (recent.length === 0) {
    return <div className="text-[9px] text-[#444] px-2 py-3 text-center">No file changes yet</div>;
  }

  return (
    <div className="space-y-0.5">
      {recent.map((change, i) => {
        const fileName = change.path.split("/").pop() || change.path;
        const time = new Date(change.timestamp).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
        return (
          <div key={`${change.path}-${i}`} className="flex items-center gap-1.5 px-2 py-[3px] text-[9px] hover:bg-white/[0.02] rounded transition-colors">
            <span className="text-[#444] tabular-nums shrink-0 w-[36px]">{time}</span>
            <span className={clsx(
              "shrink-0 w-[32px] text-center rounded px-1 py-0.5 text-[7px] font-bold uppercase tracking-wider",
              change.action === "edit" && "text-[#ffcc44] bg-[#ffcc44]/8",
              change.action === "write" && "text-[#cc88ff] bg-[#cc88ff]/8",
              change.action === "create" && "text-[#00ff88] bg-[#00ff88]/8",
            )}>
              {change.action === "edit" ? "MOD" : change.action === "write" ? "WRT" : "NEW"}
            </span>
            <span className="text-[#888] truncate flex-1">{fileName}</span>
            {change.linesAdded && <span className="text-[#00ff88]/50 tabular-nums shrink-0">+{change.linesAdded}</span>}
            {change.linesRemoved && <span className="text-[#ff4444]/50 tabular-nums shrink-0">-{change.linesRemoved}</span>}
          </div>
        );
      })}
    </div>
  );
}

/* ── WorkTree Panel ── */
export function WorkTree({ events }: { events: FeedEvent[] }) {
  const [activeTab, setActiveTab] = useState<"tree" | "log">("tree");
  const [collapsed, setCollapsed] = useState(false);

  const changes = useMemo(() => extractFileChanges(events), [events]);
  const tree = useMemo(() => buildTree(changes), [changes]);

  const totalFiles = new Set(changes.filter(c => c.action !== "search" && c.action !== "exec").map(c => c.path)).size;
  const totalEdits = changes.filter(c => c.action === "edit" || c.action === "write" || c.action === "create").length;
  const totalAdded = changes.reduce((sum, c) => sum + (c.linesAdded || 0), 0);
  const totalRemoved = changes.reduce((sum, c) => sum + (c.linesRemoved || 0), 0);

  return (
    <div className={clsx(
      "flex flex-col border-l border-[#1a1a1a] bg-[#030303] transition-all duration-200",
      collapsed ? "w-[32px]" : "w-[280px]"
    )}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-[#1a1a1a]">
        {!collapsed && (
          <>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#555" strokeWidth="1.5" strokeLinecap="round">
              <path d="M1 3h3l1 1h5a1 1 0 011 1v5a1 1 0 01-1 1H2a1 1 0 01-1-1V3z" />
            </svg>
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#555]">
              WorkTree
            </span>
            <span className="text-[8px] text-[#444] tabular-nums ml-auto">
              {totalFiles} files
            </span>
          </>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-[#444] hover:text-[#888] transition-colors p-0.5"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            {collapsed ? (
              <polyline points="3 2 7 5 3 8" />
            ) : (
              <polyline points="7 2 3 5 7 8" />
            )}
          </svg>
        </button>
      </div>

      {!collapsed && (
        <>
          {/* Stats bar */}
          <div className="flex items-center gap-3 px-3 py-1.5 border-b border-[#1a1a1a]/60 text-[8px] text-[#555]">
            <span>{totalEdits} changes</span>
            {totalAdded > 0 && <span className="text-[#00ff88]/50">+{totalAdded}</span>}
            {totalRemoved > 0 && <span className="text-[#ff4444]/50">-{totalRemoved}</span>}
          </div>

          {/* Tabs */}
          <div className="flex border-b border-[#1a1a1a]/60">
            <button
              onClick={() => setActiveTab("tree")}
              className={clsx(
                "flex-1 py-1.5 text-[9px] font-medium text-center transition-colors",
                activeTab === "tree" ? "text-[#e8e8e8] border-b border-[#00ff88]" : "text-[#555] hover:text-[#888]"
              )}
            >
              Files
            </button>
            <button
              onClick={() => setActiveTab("log")}
              className={clsx(
                "flex-1 py-1.5 text-[9px] font-medium text-center transition-colors",
                activeTab === "log" ? "text-[#e8e8e8] border-b border-[#00ff88]" : "text-[#555] hover:text-[#888]"
              )}
            >
              Changelog
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto py-1">
            {activeTab === "tree" ? (
              tree.children.size > 0 ? (
                Array.from(tree.children.values())
                  .sort((a, b) => {
                    if (a.type === "dir" && b.type !== "dir") return -1;
                    if (a.type !== "dir" && b.type === "dir") return 1;
                    return a.name.localeCompare(b.name);
                  })
                  .map((child) => (
                    <TreeNodeItem key={child.fullPath} node={child} depth={0} />
                  ))
              ) : (
                <div className="text-[9px] text-[#444] px-2 py-6 text-center">
                  No files touched yet
                </div>
              )
            ) : (
              <ChangeLog changes={changes} />
            )}
          </div>
        </>
      )}
    </div>
  );
}
