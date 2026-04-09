"use client";

import type { ToolCall } from "@/lib/types";
import { getToolCategory } from "@/lib/types";
import {
  TerminalOutput,
  FileContentPreview,
  DiffBlock,
  GrepResults,
  GlobResults,
  TodoDisplay,
} from "@/components/feed/ToolDisplayCards";

export function StyledToolOutput({ tool }: { tool: ToolCall }) {
  const cat = getToolCategory(tool.tool_name);
  const input = tool.input_data || {};
  const output = tool.output_data || {};

  // Error: tool failed (must be before specialized renderers)
  if (tool.output_data?.error && Object.keys(tool.output_data).length === 1) {
    return (
      <div className="text-[10px] text-[#ff4444]/80 bg-[#ff4444]/[0.04] rounded border border-[#ff4444]/10 px-2.5 py-2 font-mono whitespace-pre-wrap break-all">
        {String(tool.output_data.error)}
      </div>
    );
  }

  if (cat === "bash" && tool.output_data) {
    return (
      <div className="space-y-2">
        {!!input.command && (
          <div className="flex items-center gap-1.5 font-mono text-[10px]">
            <span className="text-[#00ff88]/60">$</span>
            <span className="text-[#ccc]">
              {String(input.command).slice(0, 200)}
            </span>
          </div>
        )}
        <div className="rounded border border-[#1a1a1a] bg-black/30 p-2.5">
          <TerminalOutput
            stdout={String(output.stdout || "")}
            stderr={String(output.stderr || "")}
          />
        </div>
      </div>
    );
  }

  if (cat === "read" && tool.output_data) {
    const fileObj = (output.file as Record<string, unknown>) || {};
    const content = typeof fileObj.content === "string" ? fileObj.content : String(fileObj.content || "");
    const rawTotal = Number(fileObj.totalLines);
    const totalLines = Number.isFinite(rawTotal) ? rawTotal : 0;
    const filePath = String(fileObj.filePath || input.file_path || "");
    if (content) {
      return (
        <FileContentPreview
          content={content}
          totalLines={totalLines}
          filePath={filePath}
        />
      );
    }
  }

  if (
    (cat === "edit" || cat === "write") &&
    tool.output_data?.structuredPatch
  ) {
    return (
      <DiffBlock
        patch={output.structuredPatch as Array<Record<string, unknown>>}
      />
    );
  }

  if (cat === "grep" && tool.output_data) {
    return <GrepResults tool={tool} />;
  }

  if (cat === "glob" && tool.output_data) {
    return <GlobResults tool={tool} />;
  }

  if (cat === "todo" && input.todos) {
    return (
      <TodoDisplay
        todos={input.todos as Array<{ status: string; content: string }>}
      />
    );
  }

  if ((cat === "web_search" || cat === "web_fetch") && tool.output_data) {
    const text = String(
      (output as Record<string, unknown>).content ||
        (output as Record<string, unknown>).text ||
        ""
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
