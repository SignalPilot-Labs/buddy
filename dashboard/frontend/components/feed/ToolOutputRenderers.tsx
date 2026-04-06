"use client";

import type { ReactElement } from "react";
import { clsx } from "clsx";
import type { ToolCall } from "@/lib/types";
import { getToolCategory } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";
import { shortPath } from "@/components/feed/card-helpers";

export function TerminalOutput({ stdout, stderr }: { stdout: string; stderr: string }): ReactElement {
  const { t } = useTranslation();
  const text = stdout || stderr;
  if (!text) {
    return <div className="text-[9px] text-[#777] italic py-1">{t.groupedEventCard.noOutput}</div>;
  }
  const lines = text.split("\n");
  return (
    <div className="font-mono text-[10px] leading-relaxed max-h-[300px] overflow-y-auto">
      {lines.map((line, i) => (
        <div
          key={i}
          className={clsx(
            "px-0.5",
            stderr && !stdout ? "text-[#ff6666]" : "text-[#999]",
            line.startsWith("error") || line.startsWith("Error") || line.startsWith("ERR") ? "text-[#ff6666]" : "",
            line.startsWith("warning") || line.startsWith("Warning") || line.startsWith("WARN") ? "text-[#ffaa00]" : "",
          )}
        >
          {line || "\u00A0"}
        </div>
      ))}
    </div>
  );
}

export function FileContentPreview({
  content,
  totalLines,
  filePath,
}: {
  content: string;
  totalLines: number;
  filePath: string;
}): ReactElement {
  const { t } = useTranslation();
  const ext = filePath.split(".").pop()?.toLowerCase() || "";
  const lines = content.split("\n").slice(0, 30);
  return (
    <div className="rounded border border-[#1a1a1a] overflow-hidden bg-black/30">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0a0a0a] border-b border-[#1a1a1a]">
        <div className="flex gap-1">
          <span className="h-2 w-2 rounded-full bg-[#ff4444]/30" />
          <span className="h-2 w-2 rounded-full bg-[#ffaa00]/30" />
          <span className="h-2 w-2 rounded-full bg-[#00ff88]/30" />
        </div>
        <span className="text-[9px] text-[#666] flex-1 truncate">{shortPath(filePath)}</span>
        <span className="text-[9px] text-[#777] tabular-nums">
          {totalLines} {t.groupedEventCard.lines}
        </span>
        {ext && (
          <span className="text-[9px] text-[#888] bg-white/[0.04] rounded px-1 py-0.5 uppercase">{ext}</span>
        )}
      </div>
      <div className="font-mono text-[10px] leading-relaxed max-h-[250px] overflow-y-auto">
        {lines.map((line, i) => (
          <div key={i} className="flex">
            <span className="w-8 shrink-0 text-right pr-2 text-[#888] select-none">{i + 1}</span>
            <span className="text-[#888] whitespace-pre-wrap break-all">{line || "\u00A0"}</span>
          </div>
        ))}
        {totalLines > 30 && (
          <div className="px-2 py-1 text-[9px] text-[#777] text-center">
            … {totalLines - 30} {t.groupedEventCard.moreLines}
          </div>
        )}
      </div>
    </div>
  );
}

export function DiffBlock({ patch }: { patch: Array<Record<string, unknown>> }): ReactElement {
  return (
    <div className="rounded border border-[#1a1a1a] overflow-hidden bg-black/30 max-h-[400px] overflow-y-auto font-mono text-[10px]">
      {patch.map((hunk, hi) => {
        const lines = (hunk.lines as string[]) || [];
        return (
          <div key={hi}>
            <div className="text-[9px] text-[#888] px-3 py-1 bg-[#0a0a0a] border-b border-[#1a1a1a] font-semibold">
              @@ -{String(hunk.oldStart)},{String(hunk.oldLines)} +{String(hunk.newStart)},{String(hunk.newLines)} @@
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
                    isDel && "bg-[#ff4444]/[0.04]",
                  )}
                >
                  <span
                    className={clsx(
                      "w-5 shrink-0 text-center select-none text-[9px]",
                      isAdd ? "text-[#00ff88]/40" : isDel ? "text-[#ff4444]/40" : "text-[#888]",
                    )}
                  >
                    {isAdd ? "+" : isDel ? "−" : " "}
                  </span>
                  <span
                    className={clsx(
                      "whitespace-pre-wrap break-all flex-1 px-1",
                      isAdd ? "text-[#88ffbb]" : isDel ? "text-[#ff8888]" : "text-[#888]",
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

export function GrepResults({ tool }: { tool: ToolCall }): ReactElement {
  const { t } = useTranslation();
  const input = tool.input_data || {};
  const output = tool.output_data || {};
  const pattern = String(input.pattern || "");
  const content = String(
    (output as Record<string, unknown>).content ||
      (output as Record<string, unknown>).output ||
      JSON.stringify(output),
  );
  const lines = content.split("\n").filter(Boolean).slice(0, 30);

  return (
    <div className="rounded border border-[#1a1a1a] overflow-hidden bg-black/30">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0a0a0a] border-b border-[#1a1a1a]">
        <span className="text-[9px] text-[#88ffcc]">/{pattern}/</span>
        <span className="text-[9px] text-[#777]">
          {lines.length} {t.groupedEventCard.matches}
        </span>
      </div>
      <div className="font-mono text-[10px] leading-relaxed max-h-[200px] overflow-y-auto px-3 py-1.5">
        {lines.map((line, i) => (
          <div key={i} className="text-[#888]">
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

export function GlobResults({ tool }: { tool: ToolCall }): ReactElement | null {
  const { t } = useTranslation();
  const output = tool.output_data;
  if (!output) return null;
  const raw = JSON.stringify(output);
  const paths = raw.match(/[^\s"[\],{}]+\.\w+/g) || [];
  if (paths.length === 0) {
    return <pre className="text-[10px] text-[#888] whitespace-pre-wrap">{raw.slice(0, 500)}</pre>;
  }

  return (
    <div className="space-y-0.5 max-h-[200px] overflow-y-auto">
      {paths.slice(0, 20).map((p, i) => (
        <div key={i} className="flex items-center gap-1.5 text-[10px]">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#ff88aa" strokeWidth="1" opacity="0.4">
            <path d="M2.5 1h4l2 2v5.5a.5.5 0 01-.5.5h-5a.5.5 0 01-.5-.5v-7a.5.5 0 01.5-.5z" />
          </svg>
          <span className="text-[#888]">{p}</span>
        </div>
      ))}
      {paths.length > 20 && (
        <div className="text-[9px] text-[#777]">
          +{paths.length - 20} {t.groupedEventCard.more}
        </div>
      )}
    </div>
  );
}

export function TodoDisplay({
  todos,
}: {
  todos: Array<{ status: string; content: string }>;
}): ReactElement {
  return (
    <div className="space-y-1.5">
      {todos.map((todo, i) => (
        <div key={i} className="flex items-start gap-2 text-[10px]">
          <span
            className={clsx(
              "mt-0.5 shrink-0",
              todo.status === "completed"
                ? "text-[#00ff88]"
                : todo.status === "in_progress"
                  ? "text-[#ffaa00]"
                  : "text-[#777]",
            )}
          >
            {todo.status === "completed" ? (
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="2.5 5.5 4.5 7.5 8.5 3.5" />
              </svg>
            ) : todo.status === "in_progress" ? (
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.5" className="animate-pulse">
                <circle cx="5.5" cy="5.5" r="3.5" />
              </svg>
            ) : (
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2" y="2" width="7" height="7" rx="1" />
              </svg>
            )}
          </span>
          <span
            className={clsx(
              todo.status === "completed" && "text-[#666] line-through",
              todo.status === "in_progress" && "text-[#ddd]",
              todo.status === "pending" && "text-[#888]",
            )}
          >
            {todo.content}
          </span>
        </div>
      ))}
    </div>
  );
}

export function StyledToolOutput({ tool }: { tool: ToolCall }): ReactElement | null {
  const cat = getToolCategory(tool.tool_name);
  const input = tool.input_data || {};
  const output = tool.output_data || {};

  if (cat === "bash" && tool.output_data) {
    return (
      <div className="space-y-2">
        {!!input.command && (
          <div className="flex items-center gap-1.5 font-mono text-[10px]">
            <span className="text-[#00ff88]/60">$</span>
            <span className="text-[#ccc]">{String(input.command).slice(0, 200)}</span>
          </div>
        )}
        <div className="rounded border border-[#1a1a1a] bg-black/30 p-2.5">
          <TerminalOutput stdout={String(output.stdout || "")} stderr={String(output.stderr || "")} />
        </div>
      </div>
    );
  }

  if (cat === "read" && tool.output_data) {
    const fileObj = (output.file as Record<string, unknown>) || {};
    const content = String(fileObj.content || "");
    const totalLines = Number(fileObj.totalLines || 0);
    const filePath = String(fileObj.filePath || input.file_path || "");
    if (content) {
      return <FileContentPreview content={content} totalLines={totalLines} filePath={filePath} />;
    }
  }

  if ((cat === "edit" || cat === "write") && tool.output_data?.structuredPatch) {
    return <DiffBlock patch={output.structuredPatch as Array<Record<string, unknown>>} />;
  }

  if (cat === "grep" && tool.output_data) {
    return <GrepResults tool={tool} />;
  }

  if (cat === "glob" && tool.output_data) {
    return <GlobResults tool={tool} />;
  }

  if (cat === "todo" && input.todos) {
    return <TodoDisplay todos={input.todos as Array<{ status: string; content: string }>} />;
  }

  if ((cat === "web_search" || cat === "web_fetch") && tool.output_data) {
    const text = String(
      (output as Record<string, unknown>).content ||
        (output as Record<string, unknown>).text ||
        "",
    );
    if (text && text !== "undefined") {
      return (
        <div className="rounded border border-[#1a1a1a] bg-black/30 p-3 max-h-[300px] overflow-y-auto text-[10px] text-[#888] whitespace-pre-wrap break-words leading-relaxed">
          {text.slice(0, 3000)}
        </div>
      );
    }
  }

  if (tool.output_data) {
    return (
      <pre className="text-[10px] text-[#666] bg-black/20 rounded border border-[#1a1a1a] p-2.5 whitespace-pre-wrap break-all max-h-[300px] overflow-y-auto font-mono leading-relaxed">
        {JSON.stringify(tool.output_data, null, 2)}
      </pre>
    );
  }

  return null;
}
