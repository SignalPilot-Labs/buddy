"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import type { ToolCall } from "@/lib/types";
import { getToolCategory, TOOL_COLORS } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import {
  extractReadPaths,
  extractEditSummary,
} from "@/lib/groupEventHelpers";
import {
  Chevron,
  FileContentPreview,
  DiffBlock,
} from "@/components/feed/ToolDisplayCards";
import {
  fmtTime,
  fmtDuration,
  shortPath,
} from "@/components/feed/eventCardHelpers";
import { ToolCardBase } from "@/components/feed/ToolCardBase";

/* ── Child Tool Row (expandable) ── */
export function ChildToolRow({
  tool,
  isLast,
}: {
  tool: ToolCall;
  isLast: boolean;
}) {
  return <ToolCardBase tool={tool} variant="inline" isLast={isLast} />;
}

/* ── Read Group ── */
export function ReadGroupCard({
  tools,
  ts,
  totalDuration,
  label,
}: {
  tools: ToolCall[];
  ts: string;
  totalDuration: number;
  label: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [previewIdx, setPreviewIdx] = useState<number | null>(null);
  const cat = tools.length > 0 ? getToolCategory(tools[0].tool_name) : "read";
  const isRead = cat === "read";
  const paths = useMemo(
    () => (isRead ? extractReadPaths(tools) : []),
    [tools, isRead]
  );
  const colors = TOOL_COLORS[cat];
  const iconColor = colors?.iconColor || "#88ccff";
  const subtitle = useMemo(
    () =>
      isRead
        ? paths.slice(0, 3).map((p) => shortPath(p)).join(", ") +
          (paths.length > 3 ? ` +${paths.length - 3} more` : "")
        : tools
            .map((t) => {
              const inp = t.input_data || {};
              return (inp.pattern as string) || (inp.file_path as string) || "";
            })
            .filter(Boolean)
            .slice(0, 3)
            .join(", "),
    [tools, paths, isRead]
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-l-2 overflow-hidden transition-all duration-150 hover:border-l-[3px] focus-within:border-l-[3px] focus-within:outline focus-within:outline-1 focus-within:outline-white/20 focus-within:outline-offset-[-1px]"
      style={{
        borderColor: `${iconColor}14`,
        borderLeftColor: iconColor,
        backgroundColor: `${iconColor}05`,
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
      >
        <div
          className="flex items-center justify-center h-8 w-8 rounded-md shrink-0"
          style={{ backgroundColor: `${iconColor}14` }}
        >
          {getToolIcon(cat, iconColor)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-title font-medium" style={{ color: iconColor }}>
            {label}
          </div>
          {subtitle && (
            <div className="text-body text-text-secondary mt-0.5 truncate">
              {subtitle}
            </div>
          )}
        </div>
        <span className="text-caption text-text-dim tabular-nums shrink-0">
          {fmtTime(ts)}
        </span>
        {totalDuration > 0 && (
          <span className="text-caption text-text-dim tabular-nums shrink-0">
            {fmtDuration(totalDuration)}
          </span>
        )}
        <Chevron open={expanded} />
      </button>

      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="border-t border-white/[0.04] overflow-hidden"
        >
          {isRead ? (
            <div className="px-4 py-2 space-y-1 max-h-[500px] overflow-y-auto">
              {paths.map((p, i) => {
                const fileObj = (
                  tools[i]?.output_data as Record<string, unknown>
                )?.file as Record<string, unknown> | undefined;
                const totalLines = Number(fileObj?.totalLines || 0);
                return (
                  <div key={i}>
                    <button
                      onClick={() =>
                        setPreviewIdx(previewIdx === i ? null : i)
                      }
                      className="w-full flex items-center gap-2 text-content py-1 hover:bg-white/[0.02] rounded px-1 transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-1 focus-visible:outline-[#00ff88]"
                    >
                      <svg
                        width="10"
                        height="10"
                        viewBox="0 0 10 10"
                        fill="none"
                        stroke="#88ccff"
                        strokeWidth="1"
                        opacity="0.4"
                        aria-hidden="true"
                      >
                        <path d="M2.5 1h4l2 2v5.5a.5.5 0 01-.5.5h-5a.5.5 0 01-.5-.5v-7a.5.5 0 01.5-.5z" />
                      </svg>
                      <span className="text-text-secondary truncate flex-1">{p}</span>
                      {totalLines > 0 && (
                        <span className="text-text-secondary shrink-0 tabular-nums">
                          {totalLines} lines
                        </span>
                      )}
                      <Chevron open={previewIdx === i} size={8} />
                    </button>
                    {previewIdx === i && !!fileObj?.content && (
                      <div className="ml-4 mt-1 mb-2">
                        <FileContentPreview
                          content={String(fileObj.content)}
                          totalLines={totalLines}
                          filePath={p}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="max-h-[500px] overflow-y-auto">
              {tools.map((t, i) => (
                <ChildToolRow
                  key={i}
                  tool={t}
                  isLast={i === tools.length - 1}
                />
              ))}
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

/* ── Edit Group ── */
export function EditGroupCard({
  tools,
  ts,
  totalDuration,
}: {
  tools: ToolCall[];
  ts: string;
  totalDuration: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [expandedFile, setExpandedFile] = useState<number | null>(null);
  const edits = useMemo(() => extractEditSummary(tools), [tools]);
  const totalAdded = edits.reduce((s, e) => s + e.added, 0);
  const totalRemoved = edits.reduce((s, e) => s + e.removed, 0);
  const uniqueFiles = new Set(edits.map((e) => e.path)).size;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-l-2 border-[#ffcc44]/8 border-l-[#ffcc44] bg-[#ffcc44]/[0.02] overflow-hidden transition-all duration-150 hover:border-l-[3px] focus-within:border-l-[3px] focus-within:outline focus-within:outline-1 focus-within:outline-white/20 focus-within:outline-offset-[-1px]"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
      >
        <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#ffcc44]/8 shrink-0">
          {getToolIcon("edit", "#ffcc44")}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-title font-medium text-[#ffcc44]">
            Edited {uniqueFiles} file{uniqueFiles !== 1 ? "s" : ""} (
            {edits.length} changes)
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {totalAdded > 0 && (
              <span className="text-caption text-[#00ff88]/80 tabular-nums">
                +{totalAdded}
              </span>
            )}
            {totalRemoved > 0 && (
              <span className="text-caption text-[#ff4444]/80 tabular-nums">
                -{totalRemoved}
              </span>
            )}
          </div>
        </div>
        <span className="text-caption text-text-dim tabular-nums shrink-0">
          {fmtTime(ts)}
        </span>
        {totalDuration > 0 && (
          <span className="text-caption text-text-dim tabular-nums shrink-0">
            {fmtDuration(totalDuration)}
          </span>
        )}
        <Chevron open={expanded} />
      </button>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="border-t border-white/[0.04] overflow-hidden"
        >
          <div className="divide-y divide-white/[0.03]">
            {edits.map((edit, i) => (
              <div key={i}>
                <button
                  onClick={() =>
                    setExpandedFile(expandedFile === i ? null : i)
                  }
                  className="w-full flex items-center gap-2 px-4 py-2 text-content hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
                >
                  <svg
                    width="10"
                    height="10"
                    viewBox="0 0 10 10"
                    fill="none"
                    stroke="#ffcc44"
                    strokeWidth="1"
                    opacity="0.5"
                    aria-hidden="true"
                  >
                    <path d="M6.5 1L8 2.5 3 7.5H1.5V6L6.5 1z" />
                  </svg>
                  <span className="text-text-muted truncate flex-1">
                    {edit.path}
                  </span>
                  {edit.added > 0 && (
                    <span className="text-[#00ff88]/70 tabular-nums shrink-0">
                      +{edit.added}
                    </span>
                  )}
                  {edit.removed > 0 && (
                    <span className="text-[#ff4444]/70 tabular-nums shrink-0">
                      -{edit.removed}
                    </span>
                  )}
                  <Chevron open={expandedFile === i} size={8} />
                </button>
                {expandedFile === i && (() => {
                  const patch = tools[i]?.output_data?.structuredPatch;
                  const hasPatch = Array.isArray(patch) && (patch as unknown[]).length > 0;
                  const content = tools[i]?.output_data?.content ?? tools[i]?.input_data?.content;
                  const hasContent = typeof content === "string" && content.length > 0;
                  if (!hasPatch && !hasContent) return null;
                  const filePath =
                    typeof tools[i]?.output_data?.filePath === "string"
                      ? (tools[i].output_data!.filePath as string)
                      : typeof tools[i]?.input_data?.file_path === "string"
                        ? (tools[i].input_data!.file_path as string)
                        : "";
                  return (
                    <div className="px-4 pb-3">
                      {hasPatch ? (
                        <DiffBlock
                          patch={patch as Array<Record<string, unknown>>}
                        />
                      ) : (
                        <FileContentPreview
                          content={content as string}
                          totalLines={(content as string).split("\n").length}
                          filePath={filePath}
                        />
                      )}
                    </div>
                  );
                })()}
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
