"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { Run, FeedEvent, RunStatus } from "@/lib/types";
import { TERMINAL_STATUSES } from "@/lib/constants";
import { getButtonState } from "@/lib/commandState";
import { SmartButton } from "@/components/controls/SmartButton";
import { StatsRow } from "@/components/stats/StatsBar";

const PRESETS = [
  {
    label: "Wrap up",
    text: "Wrap up. Commit your progress with a clear summary of what was done and what remains, then stop.",
  },
  {
    label: "Security audit",
    text: "Focus on security. Do a security-focused review of the changes you've made so far and fix any issues you find.",
  },
  {
    label: "Fresh angle",
    text: "Step back and attack the problem from a fresh angle. Don't iterate on your existing approach — try something different.",
  },
  {
    label: "Add tests",
    text: "Focus on increasing test coverage for the code you've changed. Don't make any other changes.",
  },
];

const PLACEHOLDER_BY_STATUS: Record<string, string> = {
  running: "Message the agent...",
  paused: "Send a message to resume...",
  rate_limited: "Message the agent...",
  completed: "Continue from where you left off...",
  stopped: "Continue from where you left off...",
  error: "Continue from where you left off...",
  crashed: "Continue from where you left off...",
  killed: "Continue from where you left off...",
  completed_no_changes: "Continue from where you left off...",
};

const DEFAULT_PLACEHOLDER = "Select a run to send a message...";
const MAX_TEXTAREA_ROWS = 6;
const TEXTAREA_LINE_HEIGHT = 24; // matches leading-6
const TEXTAREA_VERTICAL_PADDING = 24; // py-3 = 12px top + 12px bottom

export interface CommandInputProps {
  runId: string | null;
  status: RunStatus | null;
  run: Run | null;
  connected: boolean;
  events: FeedEvent[];
  busy: boolean;
  onPause: () => void;
  onResume: (prompt?: string) => void;
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
    if (status === "paused") {
      // Resume — with or without a message
      const trimmed = text.trim();
      onResume(trimmed || undefined);
      setText("");
      return;
    }
    // "send" covers inject and restart depending on run status
    if (!hasText) return;
    const trimmed = text.trim();
    if (status != null && TERMINAL_STATUSES.has(status)) {
      onRestart(trimmed);
    } else {
      onInject(trimmed);
    }
    setText("");
  }, [buttonState, busy, hasText, text, status, onPause, onResume, onInject, onRestart]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        if (!hasText && status !== "paused") return;
        e.preventDefault();
        handleAction();
        return;
      }
      if (e.key === "Escape") {
        setText("");
        textareaRef.current?.blur();
      }
    },
    [hasText, status, handleAction],
  );

  const handlePresetClick = useCallback(
    (presetText: string) => {
      setText(presetText);
      textareaRef.current?.focus();
    },
    [],
  );

  return (
    <div className="border-t border-border bg-bg-card flex flex-col">
      {/* Preset chips — always visible */}
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
            className="text-caption px-2 py-1 rounded bg-white/[0.03] text-text-dim hover:bg-white/[0.06] hover:text-accent-hover transition-colors border border-border"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Textarea */}
      <div className="px-3 pt-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={2}
          disabled={!runId}
          className="w-full bg-black/40 border border-border rounded-lg px-3 py-3 text-content text-accent-hover placeholder:text-text-secondary resize-none focus-visible:outline-none focus-visible:border-[#88ccff]/40 focus-visible:ring-1 focus-visible:ring-[#88ccff]/40 focus-visible:shadow-[0_0_8px_rgba(136,204,255,0.08)] transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed leading-6 overflow-hidden"
          style={{ minHeight: "60px" }}
        />
      </div>

      {/* Stats row + action button */}
      <div className="flex items-center px-3 py-2 gap-2">
        <div className="flex-1 min-w-0">
          <StatsRow run={run} connected={connected} events={events} />
        </div>
        <SmartButton
          state={{ ...buttonState, disabled: buttonState.disabled || busy }}
          onClick={handleAction}
        />
      </div>
    </div>
  );
}
