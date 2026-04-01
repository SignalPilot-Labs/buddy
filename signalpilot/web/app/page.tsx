"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Landing / boot sequence page.
 * Shows a brief terminal-style boot animation then redirects to dashboard.
 * Gives the product a strong first impression — "infra that takes itself seriously."
 */

const BOOT_LINES = [
  { text: "signalpilot v0.1.0", delay: 0, color: "text-[var(--color-text)]" },
  { text: "initializing governance engine...", delay: 200, color: "text-[var(--color-text-dim)]" },
  { text: "├── sql_parse        ✓", delay: 400, color: "text-[var(--color-text-dim)]" },
  { text: "├── policy_check     ✓", delay: 550, color: "text-[var(--color-text-dim)]" },
  { text: "├── cost_estimate    ✓", delay: 700, color: "text-[var(--color-text-dim)]" },
  { text: "├── row_limit        ✓", delay: 850, color: "text-[var(--color-text-dim)]" },
  { text: "├── pii_redact       ✓", delay: 1000, color: "text-[var(--color-text-dim)]" },
  { text: "└── audit_log        ✓", delay: 1150, color: "text-[var(--color-text-dim)]" },
  { text: "sandbox manager: connected", delay: 1400, color: "text-[var(--color-success)]" },
  { text: "kvm acceleration: available", delay: 1550, color: "text-[var(--color-success)]" },
  { text: "", delay: 1700, color: "" },
  { text: "ready. redirecting to dashboard...", delay: 1800, color: "text-[var(--color-text-muted)]" },
];

export default function Home() {
  const router = useRouter();
  const [visibleLines, setVisibleLines] = useState<number>(0);
  const [showCursor, setShowCursor] = useState(true);

  useEffect(() => {
    // Show each line after its delay
    const timers = BOOT_LINES.map((line, i) =>
      setTimeout(() => setVisibleLines(i + 1), line.delay)
    );

    // Redirect after boot sequence
    const redirect = setTimeout(() => {
      router.push("/dashboard");
    }, 2800);

    // Cursor blink
    const cursorInterval = setInterval(() => {
      setShowCursor((prev) => !prev);
    }, 530);

    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(redirect);
      clearInterval(cursorInterval);
    };
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen -ml-56">
      <div className="w-[520px]">
        {/* Terminal window */}
        <div className="border border-[var(--color-border)] bg-[var(--color-bg-card)]">
          {/* Title bar */}
          <div className="flex items-center gap-3 px-4 py-2.5 border-b border-[var(--color-border)]">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-[var(--color-text-dim)] opacity-30" />
              <span className="w-2 h-2 bg-[var(--color-text-dim)] opacity-20" />
              <span className="w-2 h-2 bg-[var(--color-text-dim)] opacity-10" />
            </div>
            <code className="text-[10px] text-[var(--color-text-dim)] tracking-wider flex-1 text-center">
              signalpilot — boot
            </code>
          </div>

          {/* Terminal body */}
          <div className="p-5 font-mono min-h-[320px]">
            {/* Logo */}
            <div className="mb-6">
              <svg width="200" height="32" viewBox="0 0 200 32" fill="none" className="mb-4">
                {/* Terminal frame */}
                <rect x="0.5" y="0.5" width="31" height="31" stroke="#e8e8e8" strokeWidth="1" fill="none" />
                <rect x="4" y="4" width="24" height="24" fill="#050505" />
                {/* Chevron prompt */}
                <path d="M10 12L16 16L10 20" stroke="#e8e8e8" strokeWidth="1.5" strokeLinecap="square" />
                {/* Cursor line */}
                <line x1="18" y1="12" x2="18" y2="20" stroke="#e8e8e8" strokeWidth="1.5" opacity="0.6" />
                {/* Signal dot */}
                <circle cx="24" cy="8" r="2" fill="#00ff88" />
                {/* Text */}
                <text x="40" y="14" fill="#e8e8e8" fontSize="11" fontFamily="monospace" letterSpacing="0.1em">
                  SIGNALPILOT
                </text>
                <text x="40" y="26" fill="#444444" fontSize="9" fontFamily="monospace" letterSpacing="0.15em">
                  governed sandbox console
                </text>
              </svg>
              <div className="w-full h-px bg-[var(--color-border)]" />
            </div>

            {/* Boot lines */}
            <div className="space-y-1">
              {BOOT_LINES.slice(0, visibleLines).map((line, i) => (
                <div key={i} className="flex items-center gap-2 animate-fade-in">
                  {line.text === "" ? (
                    <div className="h-3" />
                  ) : (
                    <>
                      <span className="text-[10px] text-[var(--color-text-dim)] w-6 text-right tabular-nums select-none">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <code className={`text-[11px] tracking-wider ${line.color}`}>
                        {line.text}
                        {line.text.includes("✓") && (
                          <span className="text-[var(--color-success)] ml-0.5">
                            {/* checkmark already in text */}
                          </span>
                        )}
                      </code>
                    </>
                  )}
                </div>
              ))}
            </div>

            {/* Cursor */}
            {visibleLines < BOOT_LINES.length && (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] text-[var(--color-text-dim)] w-6 text-right tabular-nums select-none">
                  {String(visibleLines + 1).padStart(2, "0")}
                </span>
                <span className={`text-[11px] text-[var(--color-success)] ${showCursor ? "opacity-100" : "opacity-0"}`}>
                  _
                </span>
              </div>
            )}
          </div>

          {/* Status bar */}
          <div className="px-4 py-2 border-t border-[var(--color-border)] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 text-[9px] text-[var(--color-text-dim)] tracking-wider">
                <span className="w-1.5 h-1.5 bg-[var(--color-success)]" />
                system ready
              </span>
            </div>
            <span className="text-[9px] text-[var(--color-text-dim)] tracking-wider tabular-nums">
              v0.1.0
            </span>
          </div>
        </div>

        {/* Skip link */}
        <div className="mt-4 text-center">
          <button
            onClick={() => router.push("/dashboard")}
            className="text-[10px] text-[var(--color-text-dim)] hover:text-[var(--color-text)] transition-colors tracking-wider"
          >
            skip &rarr; dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
