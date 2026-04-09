"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Run, FeedEvent, RunStatus } from "@/lib/types";
import { TERMINAL_STATUSES } from "@/lib/constants";
import { getButtonState } from "@/lib/commandState";
import { SmartButton } from "@/components/controls/SmartButton";
import { StatsRow } from "@/components/stats/StatsBar";

const PRESETS = [
  {
    label: "Wrap up",
    text: "You're done for now \u2014 commit your progress, write a summary of what you did and what remains, then stop.",
  },
  {
    label: "Focus security",
    text: "Focus specifically on security issues next. Check the SECURITY_AUDIT.md and address the CRITICAL and HIGH findings.",
  },
  {
    label: "Run tests",
    text: "Stop making changes and run the full test suite. Report any failures.",
  },
  {
    label: "Add tests",
    text: "Focus on adding test coverage for the gateway module. Don't make any other changes.",
  },
];

const PLACEHOLDER_BY_STATUS: Record<string, string> = {
  running: "Message the agent...",
  paused: "Send a message to resume...",
  rate_limited: "Message the agent...",
  completed: "Restart with instructions...",
  stopped: "Restart with instructions...",
  error: "Restart with instructions...",
  crashed: "Restart with instructions...",
  killed: "Restart with instructions...",
  completed_no_changes: "Restart with instructions...",
};

const DEFAULT_PLACEHOLDER = "Select a run to send a message...";
const MAX_TEXTAREA_ROWS = 6;
const TEXTAREA_LINE_HEIGHT = 20;
const TEXTAREA_VERTICAL_PADDING = 20;

export interface CommandInputProps {
  runId: string | null;
  status: RunStatus | null;
  run: Run | null;
  connected: boolean;
  events: FeedEvent[];
  busy: boolean;
  onPause: () => void;
  onResume: () => void;
  onInject: (prompt: string) => void;
  onRestart: (prompt: string) => void;
}

export function CommandInput({
  runId,
  status,
  run,
  connected,
  events,
  busy,
  onPause,
  onResume,
  onInject,
  onRestart,
}: CommandInputProps): React.ReactElement {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hasText = text.trim().length > 0;
  const buttonState = getButtonState(status, hasText);
  const placeholder =
    status != null ? (PLACEHOLDER_BY_STATUS[status] ?? DEFAULT_PLACEHOLDER) : DEFAULT_PLACEHOLDER;

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = TEXTAREA_LINE_HEIGHT * MAX_TEXTAREA_ROWS + TEXTAREA_VERTICAL_PADDING;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [text, adjustHeight]);

  const handleAction = useCallback(() => {
    if (buttonState.disabled || busy) return;

    if (buttonState.icon === "pause") {
      onPause();
      return;
    }
    // "send" covers inject, resume, and restart depending on run status
    if (!hasText) return;
    const trimmed = text.trim();
    if (status === "paused") {
      onInject(trimmed);
    } else if (status != null && TERMINAL_STATUSES.has(status)) {
      onRestart(trimmed);
    } else {
      onInject(trimmed);
    }
    setText("");
  }, [buttonState, busy, hasText, text, status, onPause, onInject, onRestart]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        if (!hasText) return;
        e.preventDefault();
        handleAction();
        return;
      }
      if (e.key === "Escape") {
        setText("");
        textareaRef.current?.blur();
      }
    },
    [hasText, handleAction],
  );

  const handlePresetClick = useCallback(
    (presetText: string) => {
      setText(presetText);
      textareaRef.current?.focus();
    },
    [],
  );

  const showPresets = focused || hasText;

  return (
    <div className="border-t border-[#1a1a1a] bg-[#0a0a0a] flex flex-col">
      {/* Stats row */}
      <div className="px-3 pt-2">
        <StatsRow run={run} connected={connected} events={events} />
      </div>

      {/* Preset chips — animated reveal */}
      <AnimatePresence>
        {showPresets && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="flex gap-1.5 px-3 pt-2 flex-wrap">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handlePresetClick(p.text);
                  }}
                  onClick={() => handlePresetClick(p.text)}
                  aria-label={`Quick prompt: ${p.label}`}
                  className="text-[10px] px-2 py-1 rounded bg-white/[0.03] text-[#777] hover:bg-white/[0.06] hover:text-[#aaa] hover:bg-gradient-to-r hover:from-transparent hover:via-white/[0.01] hover:to-transparent transition-colors border border-[#1a1a1a]"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Textarea + smart button */}
      <div className="relative px-3 py-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          rows={1}
          disabled={!runId}
          className="w-full bg-black/40 border border-[#1a1a1a] rounded-lg pl-3 pr-32 py-2.5 text-[11px] text-[#ccc] placeholder-[#666] resize-none focus:outline-none focus:border-[#88ccff]/40 focus:ring-1 focus:ring-[#88ccff]/20 focus:shadow-[0_0_8px_rgba(136,204,255,0.08)] transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed leading-5"
          style={{ minHeight: "40px" }}
        />
        <div className="absolute right-5 bottom-4 flex items-center">
          <SmartButton
            state={{ ...buttonState, disabled: buttonState.disabled || busy }}
            onClick={handleAction}
          />
        </div>
        {hasText && (
          <div className="flex justify-end mt-1">
            <span className="text-[10px] text-[#444]">Enter to send · Shift+Enter for newline</span>
          </div>
        )}
      </div>
    </div>
  );
}
