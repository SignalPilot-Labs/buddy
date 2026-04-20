"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import type { FeedEvent, RunStatus } from "@/lib/types";
import type { DiffStats } from "@/lib/api";
import { fetchRunDiff, fetchDiffRepo, fetchDiffTmp } from "@/lib/api";
import {
  extractFileChanges,
  buildTreeFromDiff,
  buildTreeFromChanges,
  mergeTrees,
  parseTmpDiffStats,
  resolveSessionTree,
} from "@/lib/worktree-utils";
import type { TreeNode } from "@/lib/worktree-utils";
import { DIFF_MAX_BYTES, DIFF_POLL_INTERVAL_MS, TERMINAL_STATUSES } from "@/lib/constants";
import { FileDiffViewer } from "./FileDiffViewer";

/* ── Icons ── */
function FileIcon({ name, status }: { name: string; status?: string }) {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  let color = "#555";
  if (status === "added") color = "#00ff88";
  else if (status === "deleted") color = "#ff4444";
  else if (status === "modified") color = "#ffcc44";
  else if (ext === "tsx" || ext === "ts") color = "#3178c6";
  else if (ext === "css") color = "#264de4";
  else if (ext === "py") color = "#3776ab";
  else if (ext === "sql") color = "#e38c00";

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
      {open
        ? <><path d="M1 3.5h3l1-1h4.5a1 1 0 011 1V4H2.5L1 9V3.5z" /><path d="M2.5 4L1 9h8.5l1.5-5H2.5z" /></>
        : <path d="M1 3h3l1 1h5a1 1 0 011 1v5a1 1 0 01-1 1H2a1 1 0 01-1-1V3z" />}
    </svg>
  );
}

/* ── Tree Node Component ── */
function NodeItem({
  node,
  depth,
  onFileClick,
  clickablePaths,
}: {
  node: TreeNode;
  depth: number;
  onFileClick: ((path: string, status: string) => void) | null;
  clickablePaths: ReadonlySet<string> | null;
}) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.isDir && node.children.size > 0;

  const sorted = useMemo(() => {
    const arr = Array.from(node.children.values());
    return arr.sort((a, b) => {
      if (a.isDir && !b.isDir) return -1;
      if (!a.isDir && b.isDir) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [node.children]);

  const totalAdded = useMemo(() => {
    if (!node.isDir) return node.added;
    let sum = node.added;
    const walk = (n: TreeNode) => { sum += n.added; n.children.forEach(walk); };
    node.children.forEach(walk);
    return sum;
  }, [node]);

  const totalRemoved = useMemo(() => {
    if (!node.isDir) return node.removed;
    let sum = node.removed;
    const walk = (n: TreeNode) => { sum += n.removed; n.children.forEach(walk); };
    node.children.forEach(walk);
    return sum;
  }, [node]);

  const isClickable = !isDir && onFileClick !== null && (clickablePaths === null || clickablePaths.has(node.fullPath));

  const handleClick = () => {
    if (isDir) { setOpen(!open); return; }
    if (isClickable) onFileClick!(node.fullPath, node.status ?? "modified");
  };

  return (
    <div>
      <div
        className={clsx(
          "flex items-center gap-1.5 py-[3px] px-1 rounded transition-colors text-content",
          isDir ? "cursor-pointer" : isClickable ? "cursor-pointer" : "cursor-default",
          isClickable ? "hover:bg-white/[0.06]" : "hover:bg-white/[0.03]",
        )}
        style={{ paddingLeft: depth * 14 + 4 }}
        onClick={handleClick}
      >
        {isDir ? (
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="#888" strokeWidth="1.5" strokeLinecap="round"
            className={clsx("shrink-0 transition-transform duration-150", open && "rotate-90")}>
            <polyline points="2 1 6 4 2 7" />
          </svg>
        ) : <span className="w-2 shrink-0" />}

        {isDir ? <DirIcon open={open} /> : <FileIcon name={node.name} status={node.status} />}

        <span className={clsx("flex-1 truncate", node.status === "deleted" ? "text-accent-hover line-through" : "text-accent-hover")}>
          {node.name}
        </span>

        {(totalAdded > 0 || totalRemoved > 0) && (
          <span className="flex items-center gap-1 shrink-0">
            {totalAdded > 0 && <span className="text-caption text-[#00ff88]/70 tabular-nums">+{totalAdded}</span>}
            {totalRemoved > 0 && <span className="text-caption text-[#ff4444]/70 tabular-nums">-{totalRemoved}</span>}
          </span>
        )}

        {node.status && !node.isDir && (
          <span className={clsx(
            "text-caption font-bold uppercase tracking-wider rounded px-1 py-0.5 shrink-0",
            node.status === "added" && "text-[#00ff88]/80 bg-[#00ff88]/10",
            node.status === "modified" && "text-[#ffcc44]/80 bg-[#ffcc44]/10",
            node.status === "deleted" && "text-[#ff4444]/80 bg-[#ff4444]/10",
            node.status === "renamed" && "text-[#88ccff]/80 bg-[#88ccff]/10",
          )}>
            {node.status === "added" ? "A" : node.status === "modified" ? "M" : node.status === "deleted" ? "D" : "R"}
          </span>
        )}
      </div>

      <AnimatePresence>
        {open && isDir && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.15 }} className="overflow-hidden">
            {sorted.map(child => (
              <NodeItem key={child.fullPath} node={child} depth={depth + 1} onFileClick={onFileClick} clickablePaths={clickablePaths} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Source Badge ── */
// Only two meaningful states now that the sandbox's /diff/repo/stats diffs
// the working tree (so uncommitted edits are visible immediately): "live"
// for anything coming out of an active sandbox session, and "git" for the
// stored diff persisted at teardown. The previous "session" fallback —
// triggered when we had content from the event stream but not yet from
// git — is dead: worktree diff makes that a race that resolves in <poll
// interval. Keeping only the two real states.
type DisplaySource = "diff-live" | "diff-stored" | null;

function SourceBadge({ source }: { source: DisplaySource }) {
  if (!source) return null;

  const config: Record<NonNullable<DisplaySource>, { label: string; className: string }> = {
    "diff-live": {
      label: "live",
      className: "text-[#00ff88]/70 bg-[#00ff88]/10",
    },
    "diff-stored": {
      label: "git",
      className: "text-[#88ccff]/70 bg-[#88ccff]/10",
    },
  };

  const { label, className } = config[source];
  return (
    <span className={clsx("text-caption font-bold rounded px-1 py-0.5 uppercase tracking-wider leading-tight", className)}>
      {label}
    </span>
  );
}

/* ── Empty State ── */
type EmptyReason = "no-run" | "loading" | "unavailable" | "too-large" | "active-no-changes" | "completed-no-changes";

function EmptyState({ reason }: { reason: EmptyReason }) {
  const messages: Record<EmptyReason, string> = {
    "no-run": "Select a run to see file changes",
    loading: "Loading changes\u2026",
    unavailable: "Diff unavailable",
    "too-large": "Diff too large to display — open the PR on GitHub instead",
    "active-no-changes": "No file changes yet",
    "completed-no-changes": "No file changes in this run",
  };

  return (
    <div className="text-meta text-text-dim px-3 py-6 text-center">
      {messages[reason]}
    </div>
  );
}

/* ── Main WorkTree Panel ── */
export interface WorkTreeProps {
  events: FeedEvent[];
  runId: string | null;
  runStatus: RunStatus | null;
}

export function WorkTree({ events, runId, runStatus }: WorkTreeProps) {
  const [diffData, setDiffData] = useState<DiffStats | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  // Repo and tmp diffs are separate sources — one is git working-branch-vs-base,
  // the other is sandbox filesystem reads of `/tmp/round-*`. Keeping them as
  // distinct state avoids a combined blob that's awkward to size-cap, parse,
  // and route file-click lookups through.
  const [repoDiff, setRepoDiff] = useState<string | null>(null);
  const [tmpDiff, setTmpDiff] = useState<string | null>(null);
  const [diffTooLarge, setDiffTooLarge] = useState(false);
  const [selectedFile, setSelectedFile] = useState<{ path: string; status: string } | null>(null);

  // Fetch diff bodies (repo + tmp). Extracted so both mount and poll
  // can call it — before this, bodies were one-shot on mount so newly
  // written round reports were visible in the tree (via liveTree from
  // the event stream) but couldn't be opened until a manual refresh.
  const fetchDiffBodies = useCallback((id: string) => {
    Promise.all([
      fetchDiffRepo(id).then(d => d.diff).catch(() => ""),
      fetchDiffTmp(id).then(d => d.diff).catch(() => ""),
    ]).then(([repo, tmp]) => {
      const repoOversize = repo.length > DIFF_MAX_BYTES;
      const tmpOversize = tmp.length > DIFF_MAX_BYTES;
      const repoSafe = repoOversize ? null : (repo || null);
      const tmpSafe = tmpOversize ? null : (tmp || null);
      setRepoDiff(repoSafe);
      setTmpDiff(tmpSafe);
      setDiffTooLarge((repoOversize || tmpOversize) && !repoSafe && !tmpSafe);
    });
  }, []);

  // Fetch diff stats (file list) when run changes
  useEffect(() => {
    if (!runId) {
      setDiffData(null);
      setRepoDiff(null);
      setTmpDiff(null);
      setDiffTooLarge(false);
      return;
    }
    setSelectedFile(null);
    setDiffTooLarge(false);
    setDiffLoading(true);
    fetchRunDiff(runId)
      .then(d => { setDiffData(d); setDiffLoading(false); })
      .catch(err => {
        console.warn("WorkTree: diff stats fetch failed:", err);
        setDiffLoading(false);
      });
    fetchDiffBodies(runId);
  }, [runId]);

  // Poll all three diff sources for live/agent runs so the tree, badge,
  // and click-to-open all stay fresh mid-round. Before this, only stats
  // were polled — repoDiff and tmpDiff were one-shot on mount, so newly
  // written round reports appeared in the tree (via liveTree from events)
  // but couldn't be opened until a manual refresh fetched the diff body.
  const isPollingSource = diffData?.source === "live" || diffData?.source === "agent";
  useEffect(() => {
    if (!runId || !isPollingSource) return;
    const id = setInterval(() => {
      fetchRunDiff(runId).then(setDiffData).catch(err => console.warn("WorkTree: diff poll failed:", err));
      fetchDiffBodies(runId);
    }, DIFF_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [runId, isPollingSource]);

  // Live changes from event stream. Split tmp/round-N writes off from the
  // rest: those are always new files (correctly 'added'), while other
  // writes are mid-run edits in the working tree (correctly 'modified').
  // This lets the status badges be right during the race window where
  // /diff/tmp hasn't returned yet but the Write event is already in feed.
  const liveChanges = useMemo(() => extractFileChanges(events), [events]);
  const writeChanges = useMemo(() => liveChanges.filter(c => c.action !== "read"), [liveChanges]);
  const liveTree = useMemo(() => {
    const tmpLive = liveChanges.filter(c => c.path.startsWith("tmp/round-"));
    const repoLive = liveChanges.filter(c => !c.path.startsWith("tmp/round-"));
    return mergeTrees(
      buildTreeFromChanges(repoLive, null),
      buildTreeFromChanges(tmpLive, "added"),
    );
  }, [liveChanges]);

  // Git diff tree (from stats endpoint)
  const diffTree = useMemo(() => diffData?.files ? buildTreeFromDiff(diffData.files) : null, [diffData]);

  // Tmp tree: parsed from the dedicated /diff/tmp source. Authoritative
  // for line counts (liveTree only knows what Write events reported).
  const tmpTree = useMemo(() => {
    if (!tmpDiff) return null;
    const tmpChanges = parseTmpDiffStats(tmpDiff);
    if (tmpChanges.length === 0) return null;
    return buildTreeFromChanges(
      tmpChanges.map(c => ({
        path: c.path, action: "edit" as const,
        linesAdded: c.linesAdded, linesRemoved: 0,
        timestamp: "", toolCallId: 0, toolName: "Archive",
      })),
      "added",
    );
  }, [tmpDiff]);

  const hasGitDiff = diffData !== null && diffData.files.length > 0;
  const hasLiveChanges = writeChanges.length > 0;
  const hasTmpFiles = tmpTree !== null;
  const hasContent = hasGitDiff || hasLiveChanges || hasTmpFiles;

  // Merged tree: git diff + session (liveTree ⊕ tmpTree). Session wins
  // over git on conflict; resolveSessionTree handles the internal
  // liveTree-vs-tmpTree conflict so round-N files keep their 'added' status.
  const mergedTree = useMemo(() => {
    const sessionTree = resolveSessionTree(liveTree, tmpTree);
    if (!diffTree && !sessionTree) return null;
    if (!diffTree) return sessionTree;
    if (!sessionTree) return diffTree;
    return mergeTrees(diffTree, sessionTree);
  }, [diffTree, liveTree, tmpTree]);

  const mergedRoots = useMemo(() => {
    if (!mergedTree) return [];
    return Array.from(mergedTree.children.values())
      .sort((a, b) => a.isDir === b.isDir ? a.name.localeCompare(b.name) : a.isDir ? -1 : 1);
  }, [mergedTree]);

  // Badge: derive directly from diffData.source. "live" and "agent"
  // both mean an active sandbox → green "live"; "stored" → blue "git".
  // No more "session" fallback — worktree diff eliminated the window
  // where we had event-stream content but no git stats.
  const displaySource: DisplaySource = (() => {
    if (!hasContent) return null;
    if (!diffData) return null;
    if (diffData.source === "stored") return "diff-stored";
    return "diff-live";
  })();

  // File count from merged tree
  const headerFileCount = useMemo(() => {
    if (!mergedTree) return 0;
    let count = 0;
    const walk = (n: TreeNode) => { if (!n.isDir) count++; n.children.forEach(walk); };
    mergedTree.children.forEach(walk);
    return count;
  }, [mergedTree]);

  // Stats bar (git diff stats when available)
  const showDiffStats = hasGitDiff && diffData && (diffData.total_added > 0 || diffData.total_removed > 0);

  // Empty state reason
  const emptyReason: EmptyReason = (() => {
    if (!runId) return "no-run";
    if (diffLoading && !diffData) return "loading";
    if (diffTooLarge && !hasLiveChanges && !hasTmpFiles) return "too-large";
    if (diffData?.source === "unavailable" && !hasLiveChanges && !hasTmpFiles) return "unavailable";
    const isTerminal = runStatus !== null && TERMINAL_STATUSES.has(runStatus);
    return isTerminal ? "completed-no-changes" : "active-no-changes";
  })();

  // Each clicked path is backed by one of two diff sources: tmp/round-N
  // files come from the tmp diff, everything else from the repo diff.
  // Pick the right source here so FileDiffViewer is simple.
  const diffForPath = (path: string): string | null =>
    path.startsWith("tmp/round-") ? tmpDiff : repoDiff;

  // Always allow clicking files when the tree has content. Diff bodies
  // load async and may arrive after the tree renders — gating clicks on
  // body availability caused files to appear unclickable on first load.
  // FileDiffViewer handles the missing-body case with a loading state.
  const onFileClick = hasContent
    ? (path: string, status: string) => setSelectedFile({ path, status })
    : null;

  return (
    <div className="flex flex-col bg-sidebar h-full w-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#888" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
          <path d="M6 1v10M6 1L3 4M6 1l3 3" />
          <circle cx="6" cy="11" r="0" /><circle cx="3" cy="6" r="1" /><circle cx="9" cy="8" r="1" />
          <line x1="3" y1="6" x2="6" y2="6" /><line x1="9" y1="8" x2="6" y2="8" />
        </svg>
        <span className="text-body font-bold uppercase tracking-[0.15em] text-text-muted">Changes</span>
        <SourceBadge source={displaySource} />
        {hasContent && (
          <span className="text-meta text-text-dim tabular-nums ml-auto">{headerFileCount} files</span>
        )}
      </div>

      {/* Diff stats bar */}
      {showDiffStats && diffData && (
        <div className="flex items-center gap-3 px-3 py-1.5 border-b border-border/60 text-meta text-text-secondary">
          <span>{diffData.total_files} files changed</span>
          {diffData.total_added > 0 && <span className="text-[#00ff88]/70">+{diffData.total_added}</span>}
          {diffData.total_removed > 0 && <span className="text-[#ff4444]/70">-{diffData.total_removed}</span>}
        </div>
      )}

      {/* Content */}
      <div className={clsx("flex-1 overflow-y-auto", selectedFile === null && "py-1")}>
        {selectedFile !== null && diffForPath(selectedFile.path) !== null ? (
          <FileDiffViewer
            fullDiff={diffForPath(selectedFile.path)!}
            filePath={selectedFile.path}
            fileStatus={selectedFile.status}
            onBack={() => setSelectedFile(null)}
          />
        ) : selectedFile !== null ? (
          /* File selected but diff body still loading */
          <div>
            <button
              onClick={() => setSelectedFile(null)}
              className="flex items-center gap-1 px-3 py-2 text-content text-text-secondary hover:text-accent-hover transition-colors"
            >
              <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><polyline points="5 1 2 4 5 7" /></svg>
              Back
            </button>
            <div className="flex items-center justify-center py-8" role="status" aria-label="Loading diff">
              <div className="h-4 w-4 rounded-full border-2 border-border-subtle border-t-[#00ff88]" style={{ animation: "spin 1s linear infinite" }} />
            </div>
          </div>
        ) : (
          <>
            {!hasContent && (
              diffLoading && !diffData ? (
                <div className="flex items-center justify-center py-8" role="status" aria-label="Loading changes">
                  <div className="h-4 w-4 rounded-full border-2 border-border-subtle border-t-[#00ff88]" style={{ animation: "spin 1s linear infinite" }} />
                </div>
              ) : (
                <EmptyState reason={emptyReason} />
              )
            )}

            {hasContent && mergedRoots.map(child => (
              <NodeItem key={child.fullPath} node={child} depth={0} onFileClick={onFileClick} clickablePaths={null} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
