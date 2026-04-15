"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const OVERLAY_INITIAL = { opacity: 0 };
const OVERLAY_ANIMATE = { opacity: 1 };
const OVERLAY_EXIT = { opacity: 0 };
const PANEL_INITIAL = { opacity: 0, scale: 0.96, y: -8 };
const PANEL_ANIMATE = { opacity: 1, scale: 1, y: 0 };
const PANEL_EXIT = { opacity: 0, scale: 0.96, y: -8 };
const ANIM_TRANSITION = { duration: 0.2, ease: "easeOut" as const };

export interface StopConfirmDialogProps {
  open: boolean;
  onConfirm: (openPr: boolean) => void;
  onCancel: () => void;
}

export function StopConfirmDialog({ open, onConfirm, onCancel }: StopConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onCancel]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={OVERLAY_INITIAL}
          animate={OVERLAY_ANIMATE}
          exit={OVERLAY_EXIT}
          transition={ANIM_TRANSITION}
          className="fixed inset-0 z-[9990] flex items-center justify-center bg-black/60 frosted-glass"
          onClick={onCancel}
          aria-modal="true"
          role="dialog"
          aria-label="Stop run confirmation"
        >
          <motion.div
            initial={PANEL_INITIAL}
            animate={PANEL_ANIMATE}
            exit={PANEL_EXIT}
            transition={ANIM_TRANSITION}
            className="relative bg-[var(--color-bg-card)] border border-[var(--color-border-hover)] rounded-lg px-6 py-5 w-[360px] max-w-[92vw] shadow-[0_24px_64px_rgba(0,0,0,0.7)]"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-title font-bold text-[var(--color-text)] tracking-wide mb-1">
              Stop this run?
            </h2>
            <p className="text-meta text-[var(--color-text-muted)] mb-5">
              Open a Pull Request?
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => onConfirm(false)}
                className="px-4 py-2 rounded text-meta font-medium text-[var(--color-text-dim)] bg-white/[0.04] border border-[var(--color-border)] hover:bg-white/[0.08] hover:text-[var(--color-text)] transition-colors"
              >
                No
              </button>
              <button
                onClick={() => onConfirm(true)}
                className="px-4 py-2 rounded text-meta font-medium text-[var(--color-accent-hover)] bg-[var(--color-accent-hover)]/10 border border-[var(--color-accent-hover)]/30 hover:bg-[var(--color-accent-hover)]/20 transition-colors"
              >
                Yes
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
