"use client";

import type { ReactElement } from "react";
import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "@/hooks/useTranslation";
import { getToolIcon } from "@/components/ui/ToolIcons";
import type { ToolCall } from "@/lib/types";
import { extractEditSummary } from "@/lib/groupEvents";
import { fmtTime, fmtDuration } from "@/components/feed/card-helpers";
import { Chevron } from "@/components/feed/Chevron";
import { DiffBlock } from "@/components/feed/ToolOutputRenderers";

export function EditGroupCard({
  tools,
  ts,
  totalDuration,
}: {
  tools: ToolCall[];
  ts: string;
  totalDuration: number;
}): ReactElement {
  const { t } = useTranslation();
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
      className="rounded-lg border border-[#ffcc44]/8 bg-[#ffcc44]/[0.02] overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#ffcc44]/8 shrink-0">
          {getToolIcon("edit", "#ffcc44")}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-medium text-[#ffcc44]">
            {t.groupedEventCard.edited} {uniqueFiles}{" "}
            {uniqueFiles !== 1 ? t.groupedEventCard.files : t.groupedEventCard.file} ({edits.length}{" "}
            {t.groupedEventCard.changes})
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {totalAdded > 0 && (
              <span className="text-[9px] text-[#00ff88]/60 tabular-nums">+{totalAdded}</span>
            )}
            {totalRemoved > 0 && (
              <span className="text-[9px] text-[#ff4444]/60 tabular-nums">-{totalRemoved}</span>
            )}
          </div>
        </div>
        <span className="text-[9px] text-[#777] tabular-nums shrink-0">{fmtTime(ts)}</span>
        {totalDuration > 0 && (
          <span className="text-[9px] text-[#888] tabular-nums shrink-0">{fmtDuration(totalDuration)}</span>
        )}
        <Chevron open={expanded} size={10} />
      </button>
      {expanded && (
        <motion.div
          initial={{ height: 0 }}
          animate={{ height: "auto" }}
          className="border-t border-white/[0.04] overflow-hidden"
        >
          <div className="divide-y divide-white/[0.03]">
            {edits.map((edit, i) => (
              <div key={i}>
                <button
                  onClick={() => setExpandedFile(expandedFile === i ? null : i)}
                  className="w-full flex items-center gap-2 px-4 py-2 text-[10px] hover:bg-white/[0.02] transition-colors text-left"
                >
                  <svg
                    width="10"
                    height="10"
                    viewBox="0 0 10 10"
                    fill="none"
                    stroke="#ffcc44"
                    strokeWidth="1"
                    opacity="0.5"
                  >
                    <path d="M6.5 1L8 2.5 3 7.5H1.5V6L6.5 1z" />
                  </svg>
                  <span className="text-[#999] truncate flex-1">{edit.path}</span>
                  {edit.added > 0 && (
                    <span className="text-[#00ff88]/50 tabular-nums shrink-0">+{edit.added}</span>
                  )}
                  {edit.removed > 0 && (
                    <span className="text-[#ff4444]/50 tabular-nums shrink-0">-{edit.removed}</span>
                  )}
                  <Chevron open={expandedFile === i} size={8} />
                </button>
                {expandedFile === i && !!(tools[i]?.output_data?.structuredPatch) && (
                  <div className="px-4 pb-3">
                    <DiffBlock
                      patch={tools[i].output_data!.structuredPatch as Array<Record<string, unknown>>}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
