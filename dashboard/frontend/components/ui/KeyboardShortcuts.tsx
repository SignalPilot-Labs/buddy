"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface ShortcutRow {
  keys: string[];
  description: string;
}

const SHORTCUTS: ShortcutRow[] = [
  { keys: ["Ctrl", "B"], description: "Toggle sidebar" },
  { keys: ["N"], description: "New run" },
  { keys: ["Space"], description: "Pause / Resume active run" },
  { keys: ["End"], description: "Scroll to latest event" },
  { keys: ["?"], description: "Show shortcuts" },
  { keys: ["Esc"], description: "Close this panel" },
];

const OVERLAY_INITIAL = { opacity: 0 };
const OVERLAY_ANIMATE = { opacity: 1 };
const OVERLAY_EXIT = { opacity: 0 };
const PANEL_INITIAL = { opacity: 0, scale: 0.96, y: -8 };
const PANEL_ANIMATE = { opacity: 1, scale: 1, y: 0 };
const PANEL_EXIT = { opacity: 0, scale: 0.96, y: -8 };
const ANIM_TRANSITION = { duration: 0.2, ease: "easeOut" as const };

interface KeyboardShortcutsProps {
  open: boolean;
  onClose: () => void;
}

export function KeyboardShortcuts({ open, onClose }: KeyboardShortcutsProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const leftColumn = SHORTCUTS.slice(0, Math.ceil(SHORTCUTS.length / 2));
  const rightColumn = SHORTCUTS.slice(Math.ceil(SHORTCUTS.length / 2));

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={OVERLAY_INITIAL}
          animate={OVERLAY_ANIMATE}
          exit={OVERLAY_EXIT}
          transition={ANIM_TRANSITION}
          className="fixed inset-0 z-[9990] flex items-center justify-center bg-black/60 frosted-glass"
          onClick={onClose}
          aria-modal="true"
          role="dialog"
          aria-label="Keyboard shortcuts"
        >
          <motion.div
            initial={PANEL_INITIAL}
            animate={PANEL_ANIMATE}
            exit={PANEL_EXIT}
            transition={ANIM_TRANSITION}
            className="relative bg-[var(--color-bg-card)] border border-[var(--color-border-hover)] rounded-lg px-6 py-5 w-[480px] max-w-[92vw] shadow-[0_24px_64px_rgba(0,0,0,0.7)]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[12px] font-bold text-[var(--color-text)] tracking-wide uppercase">
                Keyboard Shortcuts
              </h2>
              <button
                onClick={onClose}
                className="p-2 rounded text-[var(--color-text-dim)] hover:text-[var(--color-accent-hover)] hover:bg-white/[0.04] transition-colors"
                aria-label="Close shortcuts panel"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <line x1="2" y1="2" x2="10" y2="10" />
                  <line x1="10" y1="2" x2="2" y2="10" />
                </svg>
              </button>
            </div>

            {/* Two-column grid */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-1">
              <ShortcutList shortcuts={leftColumn} />
              <ShortcutList shortcuts={rightColumn} />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ShortcutList({ shortcuts }: { shortcuts: ShortcutRow[] }) {
  return (
    <div className="flex flex-col gap-1">
      {shortcuts.map((row) => (
        <ShortcutRow key={row.description} row={row} />
      ))}
    </div>
  );
}

function ShortcutRow({ row }: { row: ShortcutRow }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-[var(--color-border)]/60 last:border-0">
      <span className="text-[10px] text-[var(--color-text-muted)]">{row.description}</span>
      <div className="flex items-center gap-1 shrink-0">
        {row.keys.map((key, i) => (
          <span key={i} className="flex items-center gap-1">
            <kbd className="inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[10px] font-medium text-[var(--color-accent-hover)] bg-[var(--color-border)] border border-[var(--color-border-hover)] min-w-[20px]">
              {key}
            </kbd>
            {i < row.keys.length - 1 && (
              <span className="text-[10px] text-[var(--color-text-dim)]">+</span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
