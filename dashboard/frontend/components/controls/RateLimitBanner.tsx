"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/Button";

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return "Ready";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatResetTime(epoch: number): string {
  const d = new Date(epoch * 1000);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export function RateLimitBanner({
  resetsAt,
  onRetry,
  busy,
}: {
  resetsAt: number;
  onRetry: () => void;
  busy: boolean;
}) {
  const [initialRemaining] = useState(() =>
    Math.max(1, resetsAt - Date.now() / 1000)
  );
  const [remaining, setRemaining] = useState(() =>
    Math.max(0, resetsAt - Date.now() / 1000)
  );

  useEffect(() => {
    const interval = setInterval(() => {
      setRemaining(Math.max(0, resetsAt - Date.now() / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [resetsAt]);

  const isReady = remaining <= 0;

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className={`px-4 py-3 border-b ${
        isReady
          ? "bg-[#00ff88]/[0.04] border-[#00ff88]/15"
          : "bg-[#ffaa00]/[0.04] border-[#ffaa00]/15"
      }`}
    >
      <div className="flex items-center gap-3">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke={isReady ? "#00ff88" : "#ffaa00"} strokeWidth="1.5" strokeLinecap="round" className="shrink-0">
          <circle cx="7" cy="7" r="5.5" />
          <line x1="7" y1="3.5" x2="7" y2="7" />
          <line x1="7" y1="7" x2="9.5" y2="9" />
        </svg>

        <div className="flex-1 min-w-0">
          {isReady ? (
            <span className="text-[11px] font-semibold text-[#00ff88]">
              Rate limit cleared — ready to retry
            </span>
          ) : (
            <>
              <div className="flex items-center gap-2 text-[11px]">
                <span className="font-semibold text-[#ffaa00]">
                  Out of credits
                </span>
                <span className="text-text-secondary">
                  resets {formatResetTime(resetsAt)} ({formatCountdown(remaining)})
                </span>
              </div>
              <p className="mt-1 text-[13px] text-text-secondary leading-relaxed">
                Your Claude account has hit its usage limit.
                {" "}
                <a
                  href="https://claude.ai/settings/usage"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#88ccff] hover:underline"
                >
                  Enable or increase Extra Usage
                </a>
                {" "}to continue before the reset.
              </p>
              <div className="mt-1.5 h-[2px] bg-white/[0.04] rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-[#ffaa00]/40 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${((initialRemaining - remaining) / initialRemaining) * 100}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            </>
          )}
        </div>

        <Button
          variant={isReady ? "success" : "warning"}
          size="sm"
          disabled={busy}
          onClick={onRetry}
          icon={
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M1 5a4 4 0 017-2" />
              <polyline points="6 1 8 3 6 5" />
            </svg>
          }
        >
          {isReady ? "Retry Now" : "Retry"}
        </Button>
      </div>
    </motion.div>
  );
}
