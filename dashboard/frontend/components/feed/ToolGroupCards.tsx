"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import type { ToolCall } from "@/lib/types";
import { getToolCategory } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import { extractBashCommands } from "@/lib/groupEventHelpers";
import {
  Chevron,
  TerminalOutput,
} from "@/components/feed/ToolDisplayCards";
import {
  fmtTime,
  fmtDuration,
} from "@/components/feed/eventCardHelpers";
import { ToolCardBase } from "@/components/feed/ToolCardBase";

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
          <div className="text-title font-medium text-[#00ff88]">
            Bash · {commands.length} command
            {commands.length !== 1 ? "s" : ""}
          </div>
          <div className="text-body text-text-secondary mt-0.5 truncate">
            {commands[0]?.desc || commands[0]?.cmd}
            {commands.length > 1 ? ` + ${commands.length - 1} more` : ""}
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
          <div className="rounded-b-lg overflow-hidden">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-card border-b border-border">
              <span className="h-2 w-2 rounded-full bg-[#ff4444]/30" />
              <span className="h-2 w-2 rounded-full bg-[#ffaa00]/30" />
              <span className="h-2 w-2 rounded-full bg-[#00ff88]/30" />
              <span className="text-caption text-text-dim ml-2">bash</span>
            </div>
            <div className="bg-black/40 p-3 space-y-3 max-h-[500px] overflow-y-auto font-mono text-caption">
              {commands.map((cmd, i) => (
                <div key={i}>
                  {cmd.desc && (
                    <div className="text-meta text-text-dim mb-0.5">{cmd.desc}</div>
                  )}
                  <div className="flex items-center gap-1.5">
                    <span className="text-[#00ff88]/60">$</span>
                    <span className="text-accent-hover flex-1">{cmd.cmd}</span>
                    {cmd.duration > 0 && (
                      <span className="text-text-dim">
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
          <div className="text-title font-medium text-[#66bbff]">
            Browser · {tools.length} action{tools.length !== 1 ? "s" : ""}
          </div>
          <div className="text-body text-text-secondary mt-0.5 truncate">
            {tools
              .map((t) =>
                getToolCategory(t.tool_name).replace("playwright_", "")
              )
              .join(" → ")}
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
          <div className="p-3 space-y-2 max-h-[400px] overflow-y-auto">
            {tools.map((tc, i) => {
              const cat = getToolCategory(tc.tool_name);
              const inp = tc.input_data || {};
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-caption py-1 px-2 rounded hover:bg-white/[0.02] transition-colors"
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
                    <span className="text-text-dim tabular-nums">
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
  return <ToolCardBase tool={tool} variant="card" />;
}
