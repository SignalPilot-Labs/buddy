"use client";

import type { ReactElement } from "react";
import { useState } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { useTranslation } from "@/hooks/useTranslation";
import { getToolIcon } from "@/components/ui/ToolIcons";
import type { ToolCall } from "@/lib/types";
import { getToolCategory, TOOL_COLORS } from "@/lib/types";
import { fmtTime, fmtDuration, shortPath } from "@/components/feed/card-helpers";
import { Chevron } from "@/components/feed/Chevron";
import { StyledToolOutput } from "@/components/feed/ToolOutputRenderers";

function buildSummary(tool: ToolCall): string {
  const cat = getToolCategory(tool.tool_name);
  const input = tool.input_data || {};
  switch (cat) {
    case "bash":
      return (input.description as string) || (input.command as string)?.slice(0, 100) || "";
    case "read":
      return shortPath((input.file_path as string) || "");
    case "write":
    case "edit":
      return shortPath((input.file_path as string) || "");
    case "glob":
      return (input.pattern as string) || "";
    case "grep":
      return `/${input.pattern}/ in ${shortPath((input.path as string) || "")}`;
    case "todo": {
      const todos = (input.todos as Array<{ status: string }>) || [];
      return `${todos.filter((t) => t.status === "completed").length}✓ ${todos.filter((t) => t.status === "in_progress").length}◉ ${todos.filter((t) => t.status === "pending").length}○`;
    }
    case "skill":
      return (input.skill as string) || "";
    case "tool_search":
      return (input.query as string) || "";
    case "web_search":
      return (input.query as string) || "";
    case "web_fetch":
      return (input.url as string) || "";
    default:
      return JSON.stringify(input).slice(0, 80);
  }
}

export function SingleToolCard({ tool }: { tool: ToolCall }): ReactElement {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const cat = getToolCategory(tool.tool_name);
  const colors = TOOL_COLORS[cat];
  const denied = !tool.permitted;
  const isPending = tool.phase === "pre" && !tool.output_data;
  const summary = buildSummary(tool);

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        "rounded-lg border overflow-hidden",
        denied ? "border-[#ff4444]/10 bg-[#ff4444]/[0.02]" : "border-white/[0.04] bg-white/[0.01]",
      )}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors text-left"
      >
        <span className="opacity-60 shrink-0">
          {getToolIcon(cat, denied ? "#ff4444" : colors.iconColor)}
        </span>
        <span className={clsx("text-[10px] font-semibold shrink-0", denied ? "text-[#ff4444]" : colors.text)}>
          {tool.tool_name}
        </span>
        {denied && (
          <span className="text-[9px] font-bold text-[#ff4444] bg-[#ff4444]/8 rounded px-1 py-0.5">
            {t.eventCard.denied}
          </span>
        )}
        {isPending && (
          <span className="text-[9px] text-[#ffaa00] animate-pulse">{t.groupedEventCard.running}</span>
        )}
        <span className="text-[9px] text-[#888] truncate flex-1">
          {denied ? tool.deny_reason : summary}
        </span>
        <span className="text-[9px] text-[#777] tabular-nums shrink-0">{fmtTime(tool.ts)}</span>
        {tool.duration_ms != null && (
          <span className="text-[9px] text-[#888] tabular-nums shrink-0">{fmtDuration(tool.duration_ms)}</span>
        )}
        <Chevron open={expanded} size={8} />
      </button>
      {expanded && (
        <motion.div
          initial={{ height: 0 }}
          animate={{ height: "auto" }}
          className="border-t border-white/[0.04] overflow-hidden"
        >
          <div className="p-3 space-y-2.5">
            <StyledToolOutput tool={tool} />
            {tool.input_data && cat !== "bash" && cat !== "todo" && (
              <details className="group">
                <summary className="text-[9px] text-[#777] cursor-pointer hover:text-[#666] transition-colors">
                  {t.groupedEventCard.rawInput}
                </summary>
                <pre className="mt-1 text-[9px] text-[#888] bg-black/20 rounded p-2 border border-[#1a1a1a] whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto">
                  {JSON.stringify(tool.input_data, null, 2)}
                </pre>
              </details>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
