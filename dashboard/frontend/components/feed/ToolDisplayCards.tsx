"use client";

import { clsx } from "clsx";
import type { ToolCall } from "@/lib/types";
import { shortPath } from "@/components/feed/eventCardHelpers";

/* ── Chevron ── */
export function Chevron({ open, size = 10 }: { open: boolean; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 10 10"
      fill="none"
      stroke="#888"
      strokeWidth="1.5"
      strokeLinecap="round"
      aria-hidden="true"
      className={clsx(
        "shrink-0 transition-transform duration-150",
        open && "rotate-90"
      )}
    >
      <polyline points="3 2 7 5 3 8" />
    </svg>
  );
}

/* ── TerminalOutput ── */
export function TerminalOutput({
  stdout,
  stderr,
}: {
  stdout: string;
  stderr: string;
}) {
  const text = stdout || stderr;
  if (!text)
    return (
      <div className="text-[10px] text-text-dim italic py-1">no output</div>
    );
  const allLines = text.split("\n");
  const lines = allLines.slice(0, 200);
  const outputTruncated = allLines.length > 200;
  return (
    <div className="font-mono text-[10px] leading-relaxed max-h-[300px] overflow-y-auto">
      {lines.map((line, i) => (
        <div
          key={i}
          className={clsx(
            "px-0.5",
            stderr && !stdout ? "text-[#ff6666]" : "text-text-muted",
            line.startsWith("error") ||
              line.startsWith("Error") ||
              line.startsWith("ERR")
              ? "text-[#ff6666]"
              : "",
            line.startsWith("warning") ||
              line.startsWith("Warning") ||
              line.startsWith("WARN")
              ? "text-[#ffaa00]"
              : ""
          )}
        >
          {line || "\u00A0"}
        </div>
      ))}
      {outputTruncated && (
        <div className="px-2 py-1.5 text-[10px] text-text-dim text-center border-t border-white/[0.04]">
          … {allLines.length - 200} more lines
        </div>
      )}
    </div>
  );
}

/* ── FileContentPreview ── */
export function FileContentPreview({
  content,
  totalLines,
  filePath,
}: {
  content: string;
  totalLines: number;
  filePath: string;
}) {
  const ext = filePath.split(".").pop()?.toLowerCase() || "";
  const lines = content.split("\n").slice(0, 30);
  return (
    <div className="rounded border border-border overflow-hidden bg-black/30">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-bg-card border-b border-border">
        <div className="flex gap-1">
          <span className="h-2 w-2 rounded-full bg-[#ff4444]/30" />
          <span className="h-2 w-2 rounded-full bg-[#ffaa00]/30" />
          <span className="h-2 w-2 rounded-full bg-[#00ff88]/30" />
        </div>
        <span className="text-[10px] text-text-secondary flex-1 truncate" title={filePath}>
          {shortPath(filePath)}
        </span>
        <span className="text-[10px] text-text-dim tabular-nums">
          {totalLines} lines
        </span>
        {ext && (
          <span className="text-[10px] text-text-secondary bg-white/[0.04] rounded px-1 py-0.5 uppercase">
            {ext}
          </span>
        )}
      </div>
      <div className="font-mono text-[10px] leading-relaxed max-h-[250px] overflow-y-auto">
        {lines.map((line, i) => (
          <div key={i} className="flex">
            <span className="w-8 shrink-0 text-right pr-2 text-text-secondary select-none">
              {i + 1}
            </span>
            <span className="text-text-secondary whitespace-pre-wrap break-all">
              {line || "\u00A0"}
            </span>
          </div>
        ))}
        {totalLines > 30 && (
          <div className="px-2 py-1 text-[10px] text-text-dim text-center">
            … {totalLines - 30} more lines
          </div>
        )}
      </div>
    </div>
  );
}

/* ── DiffBlock ── */
export function DiffBlock({
  patch,
}: {
  patch: Array<Record<string, unknown>>;
}) {
  return (
    <div className="rounded border border-border overflow-hidden bg-black/30 max-h-[400px] overflow-y-auto font-mono text-[10px]">
      {patch.map((hunk, hi) => {
        const lines = (hunk.lines as string[]) || [];
        return (
          <div key={hi}>
            <div className="text-[10px] text-text-secondary px-3 py-1 bg-bg-card border-b border-border font-semibold">
              @@ -{String(hunk.oldStart)},{String(hunk.oldLines)} +
              {String(hunk.newStart)},{String(hunk.newLines)} @@
            </div>
            {lines.map((line, li) => {
              const isAdd = line.startsWith("+") && !line.startsWith("+++");
              const isDel = line.startsWith("-") && !line.startsWith("---");
              return (
                <div
                  key={li}
                  className={clsx(
                    "flex",
                    isAdd && "bg-[#00ff88]/[0.04]",
                    isDel && "bg-[#ff4444]/[0.04]"
                  )}
                >
                  <span
                    className={clsx(
                      "w-5 shrink-0 text-center select-none text-[10px]",
                      isAdd
                        ? "text-[#00ff88]/60"
                        : isDel
                        ? "text-[#ff4444]/60"
                        : "text-text-secondary"
                    )}
                  >
                    {isAdd ? "+" : isDel ? "−" : " "}
                  </span>
                  <span
                    className={clsx(
                      "whitespace-pre-wrap break-all flex-1 px-1",
                      isAdd
                        ? "text-[#88ffbb]"
                        : isDel
                        ? "text-[#ff8888]"
                        : "text-text-secondary"
                    )}
                  >
                    {line.slice(1)}
                  </span>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

/* ── GrepResults ── */
export function GrepResults({ tool }: { tool: ToolCall }) {
  const input = tool.input_data || {};
  const output = tool.output_data || {};
  const pattern = String(input.pattern || "");
  const content = String(
    (output as Record<string, unknown>).content ||
      (output as Record<string, unknown>).output ||
      JSON.stringify(output)
  );
  const allLines = content.split("\n").filter(Boolean);
  const lines = allLines.slice(0, 30);
  const truncated = allLines.length > 30;

  return (
    <div className="rounded border border-border overflow-hidden bg-black/30">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-bg-card border-b border-border">
        <span className="text-[10px] text-[#88ffcc]">/{pattern}/</span>
        <span className="text-[10px] text-text-dim">
          {truncated ? `${lines.length} of ${allLines.length}` : lines.length} matches
        </span>
      </div>
      <div className="font-mono text-[10px] leading-relaxed max-h-[200px] overflow-y-auto px-3 py-1.5">
        {lines.map((line, i) => (
          <div key={i} className="text-text-secondary">
            {line}
          </div>
        ))}
        {truncated && (
          <div className="text-[10px] text-text-dim text-center py-1">
            … {allLines.length - 30} more matches
          </div>
        )}
      </div>
    </div>
  );
}

/* ── GlobResults ── */
export function GlobResults({ tool }: { tool: ToolCall }) {
  const output = tool.output_data;
  if (!output) return null;
  const raw = JSON.stringify(output);
  const paths = raw.match(/[^\s"[\],{}]+\.\w+/g) || [];
  if (paths.length === 0)
    return (
      <pre className="text-[10px] text-text-secondary whitespace-pre-wrap">
        {raw.slice(0, 500)}
      </pre>
    );

  return (
    <div className="space-y-0.5 max-h-[200px] overflow-y-auto">
      {paths.slice(0, 20).map((p, i) => (
        <div key={i} className="flex items-center gap-1.5 text-[10px]">
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 10"
            fill="none"
            stroke="#ff88aa"
            strokeWidth="1"
            opacity="0.4"
            aria-hidden="true"
          >
            <path d="M2.5 1h4l2 2v5.5a.5.5 0 01-.5.5h-5a.5.5 0 01-.5-.5v-7a.5.5 0 01.5-.5z" />
          </svg>
          <span className="text-text-secondary">{p}</span>
        </div>
      ))}
      {paths.length > 20 && paths.length - 20 > 0 && (
        <div className="text-[10px] text-text-dim">… {paths.length - 20} more files</div>
      )}
    </div>
  );
}

/* ── TodoDisplay ── */
export function TodoDisplay({
  todos,
}: {
  todos: Array<{ status: string; content: string }>;
}) {
  return (
    <div className="space-y-1.5">
      {todos.map((t, i) => (
        <div key={i} className="flex items-start gap-2 text-[10px]">
          <span
            className={clsx(
              "mt-0.5 shrink-0",
              t.status === "completed"
                ? "text-[#00ff88]"
                : t.status === "in_progress"
                ? "text-[#ffaa00]"
                : "text-text-dim"
            )}
          >
            {t.status === "completed" ? (
              <svg
                width="11"
                height="11"
                viewBox="0 0 11 11"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                aria-hidden="true"
              >
                <polyline points="2.5 5.5 4.5 7.5 8.5 3.5" />
              </svg>
            ) : t.status === "in_progress" ? (
              <svg
                width="11"
                height="11"
                viewBox="0 0 11 11"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="animate-pulse"
                aria-hidden="true"
              >
                <circle cx="5.5" cy="5.5" r="3.5" />
              </svg>
            ) : (
              <svg
                width="11"
                height="11"
                viewBox="0 0 11 11"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                aria-hidden="true"
              >
                <rect x="2" y="2" width="7" height="7" rx="1" />
              </svg>
            )}
          </span>
          <span
            className={clsx(
              t.status === "completed" && "text-text-secondary line-through",
              t.status === "in_progress" && "text-[#ddd]",
              t.status === "pending" && "text-text-secondary"
            )}
          >
            {t.content}
          </span>
        </div>
      ))}
    </div>
  );
}

