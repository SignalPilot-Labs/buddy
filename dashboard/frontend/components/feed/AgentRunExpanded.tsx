"use client";

import { motion } from "framer-motion";
import type { ToolCall } from "@/lib/types";
import { type ToolCategory } from "@/lib/types";
import { getToolIcon } from "@/components/ui/ToolIcons";
import { MarkdownContent } from "@/components/ui/MarkdownContent";
import { Chevron } from "@/components/feed/ToolDisplayCards";
import { ChildToolRow } from "@/components/feed/GroupCards";
import {
  fmtDuration,
  extractResultText,
} from "@/components/feed/eventCardHelpers";
import { SpinnerIcon } from "@/components/ui/StatusIcons";

export function AgentRunExpanded({
  tool,
  childTools,
  childSummary,
  totalChildDuration,
  prompt,
  showPrompt,
  setShowPrompt,
  finalText,
  showFinalText,
  setShowFinalText,
  isFinalizing,
}: {
  tool: ToolCall;
  childTools: ToolCall[];
  childSummary: Array<{ cat: ToolCategory; count: number }>;
  totalChildDuration: number;
  prompt: string;
  showPrompt: boolean;
  setShowPrompt: (v: boolean) => void;
  finalText: string;
  showFinalText: boolean;
  setShowFinalText: (v: boolean) => void;
  isFinalizing: boolean;
}) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="border-t border-white/[0.04] overflow-hidden"
    >
      {childTools.length > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 border-b border-white/[0.03] bg-black/10">
          <span className="text-body text-text-secondary uppercase tracking-wider">
            {childTools.length} tool calls
          </span>
          {totalChildDuration > 0 && (
            <span className="text-caption text-text-dim tabular-nums">
              {fmtDuration(totalChildDuration)}
            </span>
          )}
          <div className="flex items-center gap-2 ml-auto">
            {childSummary.map(({ cat, count }) => (
              <span
                key={cat}
                className="flex items-center gap-1 text-caption text-text-dim"
              >
                <span className="opacity-50">{getToolIcon(cat, "#888")}</span>
                <span className="tabular-nums">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {childTools.length > 0 && (
        <div className="max-h-[400px] overflow-y-auto">
          {childTools.map((ct, idx) => (
            <ChildToolRow
              key={idx}
              tool={ct}
              isLast={idx === childTools.length - 1}
            />
          ))}
        </div>
      )}

      {prompt && (
        <div className="border-t border-white/[0.03]">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowPrompt(!showPrompt);
            }}
            className="w-full flex items-center gap-2 px-4 py-2 text-body text-text-secondary hover:bg-white/[0.02] transition-colors text-left uppercase tracking-wider focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#00ff88]"
          >
            <Chevron open={showPrompt} size={8} />
            Prompt
          </button>
          {showPrompt && (
            <div className="px-4 pb-3">
              <div className="text-content text-accent-hover whitespace-pre-wrap break-words leading-relaxed bg-black/20 rounded-lg p-3 border border-white/[0.03] max-h-[200px] overflow-y-auto">
                {prompt}
              </div>
            </div>
          )}
        </div>
      )}

      {finalText && (
        <div className="border-t border-white/[0.03]">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowFinalText(!showFinalText);
            }}
            className="w-full flex items-center gap-2 px-4 py-2 text-body text-[#cc88ff]/80 hover:bg-white/[0.02] transition-colors text-left uppercase tracking-wider focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-[-2px] focus-visible:outline-[#cc88ff]"
          >
            <Chevron open={showFinalText} size={8} />
            Agent Summary
          </button>
          {showFinalText && (
            <div className="px-4 pb-3">
              <div className="bg-black/20 rounded-lg p-3 border border-[#cc88ff]/10 max-h-[300px] overflow-y-auto">
                <MarkdownContent
                  content={finalText}
                  className="text-content text-accent-hover"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {isFinalizing && (
        <div className="border-t border-white/[0.03] px-4 py-3 flex items-center gap-2">
          <SpinnerIcon color="#cc88ff" />
          <span className="text-content text-[#cc88ff]/80">
            Agent is writing its final response...
          </span>
        </div>
      )}

      {tool.output_data && !finalText && extractResultText(tool.output_data) && (
        <div className="border-t border-white/[0.03] px-4 py-3">
          <div className="text-content uppercase tracking-[0.15em] text-[#00ff88]/70 mb-1.5">
            Result
          </div>
          <div className="bg-black/20 rounded-lg p-3 border border-white/[0.03] max-h-[200px] overflow-y-auto">
            <MarkdownContent
              content={extractResultText(tool.output_data)}
              className="text-content text-text-secondary"
            />
          </div>
        </div>
      )}
    </motion.div>
  );
}
