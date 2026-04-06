"use client";

import type { ReactElement } from "react";
import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "@/hooks/useTranslation";
import { getToolIcon } from "@/components/ui/ToolIcons";
import type { ToolCall } from "@/lib/types";
import { extractBashCommands } from "@/lib/groupEvents";
import { fmtTime, fmtDuration } from "@/components/feed/card-helpers";
import { Chevron } from "@/components/feed/Chevron";
import { TerminalOutput } from "@/components/feed/ToolOutputRenderers";

export function BashGroupCard({
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
  const commands = useMemo(() => extractBashCommands(tools), [tools]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-[#00ff88]/8 bg-[#00ff88]/[0.02] overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#00ff88]/8 shrink-0">
          {getToolIcon("bash", "#00ff88")}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-medium text-[#00ff88]">
            {t.groupedEventCard.terminal} · {commands.length}{" "}
            {commands.length !== 1 ? t.groupedEventCard.commands : t.groupedEventCard.command}
          </div>
          <div className="text-[9px] text-[#888] mt-0.5 truncate">
            {commands[0]?.cmd}
            {commands.length > 1 ? ` + ${commands.length - 1} ${t.groupedEventCard.more}` : ""}
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
          <div className="rounded-b-lg overflow-hidden">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0a0a0a] border-b border-[#1a1a1a]">
              <span className="h-2 w-2 rounded-full bg-[#ff4444]/30" />
              <span className="h-2 w-2 rounded-full bg-[#ffaa00]/30" />
              <span className="h-2 w-2 rounded-full bg-[#00ff88]/30" />
              <span className="text-[9px] text-[#777] ml-2">bash</span>
            </div>
            <div className="bg-black/40 p-3 space-y-3 max-h-[500px] overflow-y-auto font-mono text-[10px]">
              {commands.map((cmd, i) => (
                <div key={i}>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[#00ff88]/60">$</span>
                    <span className="text-[#ccc] flex-1">{cmd.cmd}</span>
                    {cmd.duration > 0 && (
                      <span className="text-[9px] text-[#777]">{fmtDuration(cmd.duration)}</span>
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
