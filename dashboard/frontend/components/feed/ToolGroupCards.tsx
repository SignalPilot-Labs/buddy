"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import type { ToolCall } from "@/lib/types";
import { getToolCategory, TOOL_COLORS } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import { extractBashCommands } from "@/lib/groupEventHelpers";
import {
  Chevron,
  TerminalOutput,
} from "@/components/feed/ToolDisplayCards";
import { StyledToolOutput } from "@/components/feed/StyledToolOutput";
import {
  fmtTime,
  fmtDuration,
  shortPath,
} from "@/components/feed/eventCardHelpers";

/* ── Bash Group ── */
export function BashGroupCard({
  tools,
  ts,
  totalDuration,
}: {
  tools: ToolCall[];
  ts: string;
  totalDuration: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const commands = useMemo(() => extractBashCommands(tools), [tools]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-l-2 border-[#00ff88]/8 border-l-[#00ff88] bg-[#00ff88]/[0.02] overflow-hidden transition-all duration-150 hover:border-l-[3px] focus-within:border-l-[3px] focus-within:outline focus-within:outline-1 focus-within:outline-white/20 focus-within:outline-offset-[-1px]"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
      >
        <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#00ff88]/8 shrink-0">
          {getToolIcon("bash", "#00ff88")}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-medium text-[#00ff88]">
            Terminal · {commands.length} command
            {commands.length !== 1 ? "s" : ""}
          </div>
          <div className="text-[13px] text-text-secondary mt-0.5 truncate">
            {commands[0]?.cmd}
            {commands.length > 1 ? ` + ${commands.length - 1} more` : ""}
          </div>
        </div>
        <span className="text-[10px] text-text-dim tabular-nums shrink-0">
          {fmtTime(ts)}
        </span>
        {totalDuration > 0 && (
          <span className="text-[10px] text-text-dim tabular-nums shrink-0">
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
          <div className="rounded-b-lg overflow-hidden">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-card border-b border-border">
              <span className="h-2 w-2 rounded-full bg-[#ff4444]/30" />
              <span className="h-2 w-2 rounded-full bg-[#ffaa00]/30" />
              <span className="h-2 w-2 rounded-full bg-[#00ff88]/30" />
              <span className="text-[10px] text-text-dim ml-2">bash</span>
            </div>
            <div className="bg-black/40 p-3 space-y-3 max-h-[500px] overflow-y-auto font-mono text-[10px]">
              {commands.map((cmd, i) => (
                <div key={i}>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[#00ff88]/60">$</span>
                    <span className="text-accent-hover flex-1">{cmd.cmd}</span>
                    {cmd.duration > 0 && (
                      <span className="text-[10px] text-text-dim">
                        {fmtDuration(cmd.duration)}
                      </span>
                    )}
                  </div>
                  {cmd.output && (
                    <div className="mt-1 ml-3.5 border-l border-white/[0.04] pl-2.5">
                      <TerminalOutput
                        stdout={cmd.exitOk ? cmd.output : ""}
                        stderr={cmd.exitOk ? "" : cmd.output}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

/* ── Playwright Group ── */
export function PlaywrightGroupCard({
  tools,
  ts,
  totalDuration,
}: {
  tools: ToolCall[];
  ts: string;
  totalDuration: number;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-l-2 border-[#66bbff]/8 border-l-[#66bbff] bg-[#66bbff]/[0.02] overflow-hidden transition-all duration-150 hover:border-l-[3px] focus-within:border-l-[3px] focus-within:outline focus-within:outline-1 focus-within:outline-white/20 focus-within:outline-offset-[-1px]"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
      >
        <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#66bbff]/8 shrink-0">
          {getToolIcon("playwright_navigate", "#66bbff")}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-medium text-[#66bbff]">
            Browser · {tools.length} action{tools.length !== 1 ? "s" : ""}
          </div>
          <div className="text-[13px] text-text-secondary mt-0.5 truncate">
            {tools
              .map((t) =>
                getToolCategory(t.tool_name).replace("playwright_", "")
              )
              .join(" → ")}
          </div>
        </div>
        <span className="text-[10px] text-text-dim tabular-nums shrink-0">
          {fmtTime(ts)}
        </span>
        {totalDuration > 0 && (
          <span className="text-[10px] text-text-dim tabular-nums shrink-0">
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
          <div className="p-3 space-y-2 max-h-[400px] overflow-y-auto">
            {tools.map((tc, i) => {
              const cat = getToolCategory(tc.tool_name);
              const inp = tc.input_data || {};
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-[10px] py-1 px-2 rounded hover:bg-white/[0.02] transition-colors"
                >
                  <span className="opacity-50 shrink-0">
                    {getToolIcon(cat, "#66bbff")}
                  </span>
                  <span className="text-text-secondary flex-1">
                    {cat.replace("playwright_", "")}
                    {!!inp.url && (
                      <span className="text-[#66bbff]/80 ml-1">
                        {String(inp.url)}
                      </span>
                    )}
                    {!!inp.filename && (
                      <span className="text-[#66bbff]/80 ml-1">
                        {String(inp.filename)}
                      </span>
                    )}
                  </span>
                  {!!tc.duration_ms && (
                    <span className="text-[10px] text-text-dim tabular-nums">
                      {fmtDuration(tc.duration_ms)}
                    </span>
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

/* ── Single Tool ── */
export function SingleToolCard({ tool }: { tool: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const cat = getToolCategory(tool.tool_name);
  const colors = TOOL_COLORS[cat];
  const denied = !tool.permitted;
  const isPending = tool.phase === "pre" && !tool.output_data;

  const input = tool.input_data || {};
  let summary = "";
  switch (cat) {
    case "bash":
      summary =
        (input.description as string) ||
        (input.command as string)?.slice(0, 100) ||
        "";
      break;
    case "read":
      summary = shortPath((input.file_path as string) || "");
      break;
    case "write":
    case "edit":
      summary = shortPath((input.file_path as string) || "");
      break;
    case "glob":
      summary = (input.pattern as string) || "";
      break;
    case "grep":
      summary = `/${input.pattern}/ in ${shortPath(
        (input.path as string) || ""
      )}`;
      break;
    case "todo": {
      const todos = (input.todos as Array<{ status: string }>) || [];
      summary = `${todos.filter((t) => t.status === "completed").length}✓ ${
        todos.filter((t) => t.status === "in_progress").length
      }◉ ${todos.filter((t) => t.status === "pending").length}○`;
      break;
    }
    case "skill":
      summary = (input.skill as string) || "";
      break;
    case "tool_search":
      summary = (input.query as string) || "";
      break;
    case "web_search":
      summary = (input.query as string) || "";
      break;
    case "web_fetch":
      summary = (input.url as string) || "";
      break;
    default:
      summary = JSON.stringify(input).slice(0, 80);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        "rounded-lg border border-l-2 overflow-hidden transition-all duration-150 hover:border-l-[3px] focus-within:border-l-[3px] focus-within:outline focus-within:outline-1 focus-within:outline-white/20 focus-within:outline-offset-[-1px]",
        denied
          ? "border-[#ff4444]/10 bg-[#ff4444]/[0.02]"
          : "border-white/[0.04] bg-white/[0.01]"
      )}
      style={{ borderLeftColor: denied ? "#ff4444" : colors.iconColor }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
      >
        <span className="opacity-60 shrink-0">
          {getToolIcon(cat, denied ? "#ff4444" : colors.iconColor)}
        </span>
        <span
          className={clsx(
            "text-[12px] font-semibold shrink-0",
            denied ? "text-[#ff4444]" : colors.text
          )}
        >
          {tool.tool_name}
        </span>
        {denied && (
          <span className="text-[10px] font-bold text-[#ff4444] bg-[#ff4444]/8 rounded px-1 py-0.5">
            DENIED
          </span>
        )}
        {isPending && (
          <span className="text-[10px] text-[#ffaa00] animate-pulse">
            running
          </span>
        )}
        <span className="text-[12px] text-text-secondary truncate flex-1">
          {denied ? tool.deny_reason : summary}
        </span>
        <span className="text-[10px] text-text-dim tabular-nums shrink-0">
          {fmtTime(tool.ts)}
        </span>
        {tool.duration_ms != null && (
          <span className="text-[10px] text-text-dim tabular-nums shrink-0">
            {fmtDuration(tool.duration_ms)}
          </span>
        )}
        <Chevron open={expanded} size={8} />
      </button>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="border-t border-white/[0.04] overflow-hidden"
        >
          <div className="p-3 space-y-2.5">
            <StyledToolOutput tool={tool} />
            {tool.input_data && cat !== "bash" && cat !== "todo" && (
              <details className="group">
                <summary className="text-[10px] text-text-dim cursor-pointer hover:text-text-muted transition-colors">
                  raw input
                </summary>
                <pre className="mt-1 text-[10px] text-text-secondary bg-black/20 rounded p-2 border border-border whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto">
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
