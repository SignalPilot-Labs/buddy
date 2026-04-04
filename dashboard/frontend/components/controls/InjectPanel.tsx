"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RunStatus } from "@/lib/types";
import { Button } from "@/components/ui/Button";

const PRESETS = [
  { label: "Wrap up", text: "You're done for now \u2014 commit your progress, write a summary of what you did and what remains, then stop." },
  { label: "Focus security", text: "Focus specifically on security issues next. Check the SECURITY_AUDIT.md and address the CRITICAL and HIGH findings." },
  { label: "Run tests", text: "Stop making changes and run the full test suite. Report any failures." },
  { label: "Add tests", text: "Focus on adding test coverage for the gateway module. Don't make any other changes." },
];

const TERMINAL_STATUSES: RunStatus[] = ["stopped", "completed", "error", "crashed", "killed"];
const ACTIVE_STATUSES: RunStatus[] = ["running", "paused", "rate_limited"];
const RESUME_WITHOUT_PROMPT_STATUSES: RunStatus[] = ["paused", "rate_limited"];

function isTerminal(status: RunStatus | null): boolean {
  return status !== null && TERMINAL_STATUSES.includes(status);
}

function isActive(status: RunStatus | null): boolean {
  return status !== null && ACTIVE_STATUSES.includes(status);
}

function canResumeWithoutPrompt(status: RunStatus | null): boolean {
  return status !== null && RESUME_WITHOUT_PROMPT_STATUSES.includes(status);
}

export interface InjectPanelProps {
  open: boolean;
  onClose: () => void;
  onSend: (prompt: string) => void;
  onResumePlain: () => void;
  onStop: () => void;
  busy: boolean;
  status: RunStatus | null;
  sessionLocked: boolean;
  timeRemaining: string | null;
}

export function InjectPanel({
  open,
  onClose,
  onSend,
  onResumePlain,
  onStop,
  busy,
  status,
  sessionLocked,
  timeRemaining,
}: InjectPanelProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [open]);

  const placeholder = isTerminal(status)
    ? "Describe what to do next (required to resume)..."
    : "Type a prompt to inject into the running agent...";

  const submitLabel = isTerminal(status) ? "Resume with Prompt" : "Send to Agent";

  const isSubmitDisabled =
    ((isTerminal(status) || status === "running") && !text.trim()) || busy;

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && status === "running") return;
    if (!trimmed && canResumeWithoutPrompt(status)) {
      onResumePlain();
      setText("");
      onClose();
      return;
    }
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
    onClose();
  };

  const handleStop = () => {
    onStop();
    onClose();
  };

  const handleResumePlain = () => {
    onResumePlain();
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
          className="overflow-hidden border-b border-[#1a1a1a]"
        >
          <div className="p-4 bg-[#0a0a0a]">
            {/* Session lock badge */}
            {sessionLocked && timeRemaining && (
              <div className="flex items-center gap-1.5 mb-3">
                <svg width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="#ffaa00" strokeWidth="1.2" opacity="0.7">
                  <rect x="1.5" y="4.5" width="6" height="3.5" rx="0.5" />
                  <path d="M3 4.5V3a1.5 1.5 0 013 0v1.5" />
                </svg>
                <span className="text-[10px] text-[#ffaa00]/70">
                  Session locked · {timeRemaining} remaining
                </span>
              </div>
            )}

            {/* Presets */}
            <div className="flex gap-1.5 mb-3 flex-wrap">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setText(p.text)}
                  className="text-[9px] px-2 py-1 rounded bg-white/[0.03] text-[#777] hover:bg-white/[0.06] hover:text-[#aaa] transition-colors border border-[#1a1a1a]"
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={3}
              className="w-full bg-black/40 border border-[#1a1a1a] rounded px-3 py-2.5 text-[11px] text-[#ccc] placeholder-[#666] resize-y focus:outline-none focus:border-[#00ff88]/30 transition-all"
            />

            {/* Actions */}
            <div className="flex items-center justify-between mt-2.5">
              {/* Left: Stop button (only when active) */}
              <div>
                {isActive(status) && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleStop}
                    disabled={busy}
                    icon={
                      <svg width="9" height="9" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <rect x="2" y="2" width="6" height="6" rx="0.5" />
                      </svg>
                    }
                  >
                    Stop
                  </Button>
                )}
              </div>

              {/* Right: Cancel / Resume without prompt / Send */}
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={onClose}
                  icon={
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <line x1="2" y1="2" x2="8" y2="8" /><line x1="8" y1="2" x2="2" y2="8" />
                    </svg>
                  }
                >
                  Cancel
                </Button>

                {canResumeWithoutPrompt(status) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleResumePlain}
                    disabled={busy}
                  >
                    Resume without prompt
                  </Button>
                )}

                <Button
                  variant="primary"
                  size="md"
                  onClick={handleSend}
                  disabled={isSubmitDisabled}
                  icon={
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                      <path d="M1 5h7M6 2l3 3-3 3" />
                    </svg>
                  }
                >
                  {submitLabel}
                </Button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
