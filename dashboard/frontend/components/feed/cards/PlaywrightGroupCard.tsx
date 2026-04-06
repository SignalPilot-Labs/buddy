"use client";

import type { ReactElement } from "react";
import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "@/hooks/useTranslation";
import { getToolIcon } from "@/components/ui/ToolIcons";
import type { ToolCall } from "@/lib/types";
import { getToolCategory } from "@/lib/types";
import { fmtTime, fmtDuration } from "@/components/feed/card-helpers";
import { Chevron } from "@/components/feed/Chevron";

export function PlaywrightGroupCard({
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-[#66bbff]/8 bg-[#66bbff]/[0.02] overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#66bbff]/8 shrink-0">
          {getToolIcon("playwright_navigate", "#66bbff")}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-medium text-[#66bbff]">
            {t.groupedEventCard.browser} · {tools.length}{" "}
            {tools.length !== 1 ? t.groupedEventCard.actions : t.groupedEventCard.action}
          </div>
          <div className="text-[9px] text-[#888] mt-0.5 truncate">
            {tools.map((tc) => getToolCategory(tc.tool_name).replace("playwright_", "")).join(" → ")}
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
          <div className="p-3 space-y-2 max-h-[400px] overflow-y-auto">
            {tools.map((tc, i) => {
              const cat = getToolCategory(tc.tool_name);
              const inp = tc.input_data || {};
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-[10px] py-1 px-2 rounded hover:bg-white/[0.02] transition-colors"
                >
                  <span className="opacity-50 shrink-0">{getToolIcon(cat, "#66bbff")}</span>
                  <span className="text-[#888] flex-1">
                    {cat.replace("playwright_", "")}
                    {!!inp.url && <span className="text-[#66bbff]/60 ml-1">{String(inp.url)}</span>}
                    {!!inp.filename && (
                      <span className="text-[#66bbff]/60 ml-1">{String(inp.filename)}</span>
                    )}
                  </span>
                  {!!tc.duration_ms && (
                    <span className="text-[9px] text-[#777] tabular-nums">{fmtDuration(tc.duration_ms)}</span>
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
