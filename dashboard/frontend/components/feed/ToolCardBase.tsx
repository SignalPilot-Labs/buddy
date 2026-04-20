"use client";

/**
 * Shared base for single tool rendering — used as both a standalone card
 * (SingleToolCard) and an inline row inside groups (ChildToolRow).
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import type { ToolCall, ToolCategory } from "@/lib/types";
import { getToolCategory, TOOL_COLORS } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import { Chevron } from "@/components/feed/ToolDisplayCards";
import { StyledToolOutput } from "@/components/feed/StyledToolOutput";
import {
  fmtTime,
  fmtDuration,
  shortPath,
} from "@/components/feed/eventCardHelpers";
import { TOOL_CATEGORIES_DEFAULT_EXPANDED } from "@/lib/constants";

type Variant = "card" | "inline";

interface ToolCardBaseProps {
  tool: ToolCall;
  variant: Variant;
  isLast?: boolean;
}

/** Build one-line summary from tool input data. */
export function buildSummary(tool: ToolCall, cat: ToolCategory): string {
  const input = tool.input_data || {};
  switch (cat) {
    case "bash":
      return (input.command as string)?.slice(0, 100) || (input.description as string) || "";
    case "read":
      return shortPath((input.file_path as string) || "");
    case "write":
    case "edit":
      return shortPath((input.file_path as string) || "");
    case "glob":
      return (input.pattern as string) || "";
    case "grep": {
      const grepPath = (input.path as string) || "";
      return `/${input.pattern}/${grepPath ? ` in ${shortPath(grepPath)}` : ""}`;
    }
    case "todo": {
      const todos = (input.todos as Array<{ status: string }>) || [];
      return `${todos.filter((t) => t.status === "completed").length}✓ ${todos.filter((t) => t.status === "in_progress").length}◉ ${todos.filter((t) => t.status === "pending").length}○`;
    }
    case "skill":
      return (input.skill as string) || "";
    case "tool_search":
    case "web_search":
      return (input.query as string) || "";
    case "web_fetch":
      return (input.url as string) || "";
    default:
      return JSON.stringify(input).slice(0, 80);
  }
}

export function ToolCardBase({ tool, variant, isLast }: ToolCardBaseProps) {
  const cat = getToolCategory(tool.tool_name);
  const colors = TOOL_COLORS[cat];
  const defaultExpanded = variant === "card" && TOOL_CATEGORIES_DEFAULT_EXPANDED.has(cat);
  const [expanded, setExpanded] = useState(defaultExpanded);

  const denied = variant === "card" && !tool.permitted;
  const isPending = variant === "card" && tool.phase === "pre" && !tool.output_data;
  const hasOutput = !!tool.output_data;
  const summary = denied ? (tool.deny_reason || "") : buildSummary(tool, cat);
  const iconColor = denied ? "#ff4444" : (colors?.iconColor || "#888");

  const isCard = variant === "card";

  const headerContent = (
    <>
      <span className={clsx("shrink-0", isCard ? "opacity-60" : "opacity-50")}>
        {getToolIcon(cat, iconColor)}
      </span>
      <span
        className={clsx(
          "shrink-0 font-medium",
          denied ? "text-[#ff4444]" : (colors?.text || "text-text-secondary"),
          isCard && "font-semibold",
        )}
      >
        {tool.tool_name}
      </span>
      {denied && (
        <span className="text-caption font-bold text-[#ff4444] bg-[#ff4444]/8 rounded px-1 py-0.5">
          DENIED
        </span>
      )}
      {isPending && (
        <span className="text-caption text-[#ffaa00] animate-pulse">running</span>
      )}
      <span className={clsx("truncate flex-1 min-w-0", isCard ? "text-content text-text-secondary" : "text-text-secondary")} title={summary}>
        {summary}
      </span>
      {isCard && (
        <span className="text-caption text-text-dim tabular-nums shrink-0">
          {fmtTime(tool.ts)}
        </span>
      )}
      {!!tool.duration_ms && (
        <span className="text-caption text-text-dim tabular-nums shrink-0">
          {fmtDuration(tool.duration_ms)}
        </span>
      )}
      {(isCard || hasOutput) && <Chevron open={expanded} size={8} />}
    </>
  );

  const expandedContent = expanded && (isCard || hasOutput) && (
    <div className={isCard ? "border-t border-white/[0.04] overflow-hidden" : undefined}>
      <div className={isCard ? "p-3 space-y-2.5" : "px-4 pb-2"}>
        <StyledToolOutput tool={tool} />
        {isCard && tool.input_data && cat !== "bash" && cat !== "todo" && (
          <details className="group">
            <summary className="text-caption text-text-dim cursor-pointer hover:text-accent-hover transition-colors">
              raw input
            </summary>
            <pre className="mt-1 text-caption text-text-secondary bg-black/20 rounded p-2 border border-border whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto">
              {JSON.stringify(tool.input_data, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );

  if (!isCard) {
    return (
      <div className={expanded || isLast ? undefined : "border-b border-white/[0.02]"}>
        <button
          onClick={() => hasOutput && setExpanded(!expanded)}
          className={clsx(
            "flex items-center gap-2 px-4 py-1.5 text-content w-full text-left transition-colors",
            hasOutput ? "hover:bg-white/[0.02] cursor-pointer" : "cursor-default",
          )}
        >
          {headerContent}
        </button>
        {expandedContent}
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        "rounded-lg border border-l-2 overflow-hidden transition-all duration-150 hover:border-l-[3px] focus-within:border-l-[3px] focus-within:outline focus-within:outline-1 focus-within:outline-white/20 focus-within:outline-offset-[-1px]",
        denied
          ? "border-[#ff4444]/10 bg-[#ff4444]/[0.02]"
          : "border-white/[0.04] bg-white/[0.01]",
      )}
      style={{ borderLeftColor: iconColor }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
      >
        {headerContent}
      </button>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          {expandedContent}
        </motion.div>
      )}
    </motion.div>
  );
}
