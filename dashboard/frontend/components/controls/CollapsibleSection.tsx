"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export interface CollapsibleSectionProps {
  label: string;
  summary: string;
  defaultOpen: boolean;
  children: React.ReactNode;
}

const CHEVRON_VARIANTS = { closed: { rotate: 0 }, open: { rotate: 90 } };
const CONTENT_VARIANTS = { closed: { height: 0, opacity: 0 }, open: { height: "auto", opacity: 1 } };
const SPRING_TRANSITION = { type: "spring" as const, stiffness: 400, damping: 30 };

export function CollapsibleSection({
  label,
  summary,
  defaultOpen,
  children,
}: CollapsibleSectionProps): React.ReactElement {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 py-2 rounded hover:bg-white/[0.03] transition-colors text-left"
        aria-expanded={open}
      >
        <motion.span
          variants={CHEVRON_VARIANTS}
          animate={open ? "open" : "closed"}
          transition={SPRING_TRANSITION}
          className="shrink-0 text-text-muted"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <polyline points="3 2 7 5 3 8" />
          </svg>
        </motion.span>
        <span className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold flex-1">
          {label}
        </span>
        <AnimatePresence initial={false}>
          {!open && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="text-content text-text-secondary shrink-0"
            >
              {summary}
            </motion.span>
          )}
        </AnimatePresence>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            variants={CONTENT_VARIANTS}
            initial="closed"
            animate="open"
            exit="closed"
            transition={SPRING_TRANSITION}
            style={{ overflow: "hidden" }}
          >
            <div className="pt-2">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
