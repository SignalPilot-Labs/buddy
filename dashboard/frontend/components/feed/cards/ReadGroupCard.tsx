"use client";

import type { ReactElement } from "react";
import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "@/hooks/useTranslation";
import { getToolIcon } from "@/components/ui/ToolIcons";
import type { ToolCall } from "@/lib/types";
import { extractReadPaths } from "@/lib/groupEvents";
import { fmtTime, fmtDuration, shortPath } from "@/components/feed/card-helpers";
import { Chevron } from "@/components/feed/Chevron";
import { FileContentPreview } from "@/components/feed/ToolOutputRenderers";

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
}): ReactElement {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [previewIdx, setPreviewIdx] = useState<number | null>(null);
  const paths = useMemo(() => extractReadPaths(tools), [tools]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-[#88ccff]/8 bg-[#88ccff]/[0.02] overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#88ccff]/8 shrink-0">
          {getToolIcon("read", "#88ccff")}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-medium text-[#88ccff]">{label}</div>
          <div className="text-[9px] text-[#888] mt-0.5 truncate">
            {paths.slice(0, 3).map((p) => shortPath(p)).join(", ")}
            {paths.length > 3 && ` +${paths.length - 3} ${t.groupedEventCard.more}`}
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
          <div className="px-4 py-2 space-y-1 max-h-[500px] overflow-y-auto">
            {paths.map((p, i) => {
              const fileObj = (tools[i]?.output_data as Record<string, unknown>)?.file as
                | Record<string, unknown>
                | undefined;
              const totalLines = Number(fileObj?.totalLines || 0);
              return (
                <div key={i}>
                  <button
                    onClick={() => setPreviewIdx(previewIdx === i ? null : i)}
                    className="w-full flex items-center gap-2 text-[10px] py-1 hover:bg-white/[0.02] rounded px-1 transition-colors text-left"
                  >
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 10 10"
                      fill="none"
                      stroke="#88ccff"
                      strokeWidth="1"
                      opacity="0.4"
                    >
                      <path d="M2.5 1h4l2 2v5.5a.5.5 0 01-.5.5h-5a.5.5 0 01-.5-.5v-7a.5.5 0 01.5-.5z" />
                    </svg>
                    <span className="text-[#888] truncate flex-1">{p}</span>
                    {totalLines > 0 && (
                      <span className="text-[9px] text-[#888] shrink-0 tabular-nums">
                        {totalLines} {t.groupedEventCard.lines}
                      </span>
                    )}
                    <Chevron open={previewIdx === i} size={8} />
                  </button>
                  {previewIdx === i && !!(fileObj?.content) && (
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
        </motion.div>
      )}
    </motion.div>
  );
}
