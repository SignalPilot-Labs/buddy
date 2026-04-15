"use client";

import { useState, useEffect, useRef } from "react";
import { clsx } from "clsx";
import type { ThemedToken } from "shiki";
import { fetchFileDiff } from "@/lib/api";
import type { FileDiffResponse } from "@/lib/api";
import { parseDiffLines, langFromPath } from "@/lib/diff-utils";
import type { DiffLine } from "@/lib/diff-utils";

export interface FileDiffViewerProps {
  runId: string;
  filePath: string;
  fileStatus: string;
  onBack: () => void;
}

/* ── Shiki singleton ── */
type ShikiHighlighter = Awaited<ReturnType<typeof import("shiki").createHighlighter>>;
let highlighterPromise: Promise<ShikiHighlighter> | null = null;

function getHighlighter(): Promise<ShikiHighlighter> {
  if (!highlighterPromise) {
    highlighterPromise = import("shiki").then(({ createHighlighter }) =>
      createHighlighter({
        themes: ["github-dark"],
        langs: [
          "python", "typescript", "javascript", "markdown",
          "css", "json", "html", "sql", "bash", "yaml", "go", "rust",
        ],
      }),
    );
  }
  return highlighterPromise;
}

/* ── Token renderer ── */
function HighlightedLine({
  content,
  lang,
  highlighter,
}: {
  content: string;
  lang: string;
  highlighter: ShikiHighlighter | null;
}) {
  if (!highlighter || !content.trim()) {
    return <span className="text-text-secondary">{content || "\u00a0"}</span>;
  }

  let lines: ThemedToken[][];
  try {
    const result = highlighter.codeToTokens(content, {
      lang: lang as Parameters<ShikiHighlighter["codeToTokens"]>[1]["lang"],
      theme: "github-dark",
    });
    lines = result.tokens;
  } catch (err) {
    console.warn("shiki tokenization failed:", err);
    return <span className="text-text-secondary">{content || "\u00a0"}</span>;
  }

  const tokens = lines[0] ?? [];
  if (tokens.length === 0) return <span>{content || "\u00a0"}</span>;

  return (
    <>
      {tokens.map((tok, i) => (
        <span key={i} style={{ color: tok.color ?? undefined }}>
          {tok.content}
        </span>
      ))}
    </>
  );
}

/* ── Gutter cell ── */
function GutterCell({ value }: { value: number | null }) {
  return (
    <span
      className="w-10 inline-block text-right pr-2 select-none text-text-dim shrink-0 tabular-nums"
    >
      {value !== null ? value : ""}
    </span>
  );
}

/* ── Single diff row ── */
function DiffLineRow({
  line,
  lang,
  highlighter,
}: {
  line: DiffLine;
  lang: string;
  highlighter: ShikiHighlighter | null;
}) {
  const rowClass = clsx(
    "flex items-start font-mono text-content leading-relaxed",
    line.type === "add" && "bg-[#00ff88]/[0.10]",
    line.type === "remove" && "bg-[#ff4444]/[0.10]",
  );

  if (line.type === "hunk-header") {
    return (
      <div className={clsx("font-mono text-content text-[#88ccff]/60 px-2 py-0.5 leading-relaxed")}>
        {line.content}
      </div>
    );
  }

  if (line.type === "meta") {
    return (
      <div className="font-mono text-content text-text-dim px-2 py-0.5 leading-relaxed">
        {line.content}
      </div>
    );
  }

  const prefix = line.type === "add" ? "+" : line.type === "remove" ? "-" : " ";
  const prefixColor =
    line.type === "add" ? "text-[#00ff88]/70" : line.type === "remove" ? "text-[#ff4444]/70" : "text-text-dim";

  return (
    <div className={rowClass}>
      <GutterCell value={line.oldLine} />
      <GutterCell value={line.newLine} />
      <span className={clsx("pr-2 select-none shrink-0", prefixColor)}>{prefix}</span>
      <span className="flex-1 overflow-x-auto whitespace-pre">
        <HighlightedLine content={line.content} lang={lang} highlighter={highlighter} />
      </span>
    </div>
  );
}

/* ── Status badge ── */
function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, string> = {
    added: "text-[#00ff88]/80 bg-[#00ff88]/10",
    modified: "text-[#ffcc44]/80 bg-[#ffcc44]/10",
    deleted: "text-[#ff4444]/80 bg-[#ff4444]/10",
    renamed: "text-[#88ccff]/80 bg-[#88ccff]/10",
  };
  const cls = cfg[status] ?? "text-text-dim bg-white/5";
  return (
    <span className={clsx("text-caption font-bold uppercase tracking-wider rounded px-1 py-0.5", cls)}>
      {status}
    </span>
  );
}

/* ── Main component ── */
export function FileDiffViewer({ runId, filePath, fileStatus, onBack }: FileDiffViewerProps) {
  const [diffData, setDiffData] = useState<FileDiffResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [highlighter, setHighlighter] = useState<ShikiHighlighter | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    setError(null);
    setDiffData(null);

    fetchFileDiff(runId, filePath)
      .then((data) => {
        if (mountedRef.current) {
          setDiffData(data);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (mountedRef.current) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      mountedRef.current = false;
    };
  }, [runId, filePath]);

  useEffect(() => {
    getHighlighter().then((h) => {
      if (mountedRef.current) setHighlighter(h);
    }).catch((err: unknown) => {
      console.warn("shiki highlighter init failed:", err);
    });
  }, []);

  const lang = langFromPath(filePath);
  const diffLines = diffData?.patch ? parseDiffLines(diffData.patch) : [];

  return (
    <div className="flex flex-col bg-sidebar h-full w-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-2 py-2 border-b border-border shrink-0">
        <button
          onClick={onBack}
          className="p-2 rounded hover:bg-white/[0.06] transition-colors text-text-dim hover:text-text min-w-[44px] min-h-[44px] flex items-center justify-center"
          aria-label="Back to file tree"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <polyline points="7 2 3 6 7 10" />
          </svg>
        </button>
        <span className="flex-1 text-content text-accent-hover font-mono truncate" title={filePath}>
          {filePath}
        </span>
        <StatusBadge status={fileStatus} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        {loading && (
          <div className="flex items-center justify-center py-8" role="status" aria-label="Loading diff">
            <div
              className="h-4 w-4 rounded-full border-2 border-border-subtle border-t-[#00ff88]"
              style={{ animation: "spin 1s linear infinite" }}
            />
          </div>
        )}

        {!loading && error !== null && (
          <div className="px-3 py-6 text-center text-meta text-[#ff4444]/80">
            {error}
          </div>
        )}

        {!loading && error === null && diffData !== null && diffData.binary && (
          <div className="px-3 py-6 text-center text-meta text-text-dim">
            Binary file — diff not available
          </div>
        )}

        {!loading && error === null && diffData !== null && !diffData.binary && diffData.empty && (
          <div className="px-3 py-6 text-center text-meta text-text-dim">
            File unchanged in this diff
          </div>
        )}

        {!loading && error === null && diffData !== null && !diffData.binary && !diffData.empty && (
          <div className="text-content font-mono py-1">
            {diffLines.map((line, idx) => (
              <DiffLineRow
                key={idx}
                line={line}
                lang={lang}
                highlighter={highlighter}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
