"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { PINNED_BRANCHES } from "@/lib/constants";

export interface BranchPickerProps {
  branches: string[];
  selected: string;
  onSelect: (b: string) => void;
}

export function BranchPicker({ branches, selected, onSelect }: BranchPickerProps): React.ReactElement {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = query
    ? branches.filter((b) => b.toLowerCase().includes(query.toLowerCase()))
    : branches;

  const sorted = [...filtered].sort((a, b) => {
    const aPin = PINNED_BRANCHES.indexOf(a);
    const bPin = PINNED_BRANCHES.indexOf(b);
    if (aPin !== -1 && bPin !== -1) return aPin - bPin;
    if (aPin !== -1) return -1;
    if (bPin !== -1) return 1;
    return a.localeCompare(b);
  });

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">
        Branch from
      </label>
      <button
        onClick={() => setOpen(!open)}
        className="mt-1.5 w-full flex items-center justify-between px-3 py-2 bg-black/30 border border-border rounded text-content text-left hover:border-border-hover transition-colors"
      >
        <span className="font-mono text-text">{selected}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#999" strokeWidth="1.5" strokeLinecap="round">
          <polyline points="2 4 5 6 8 4" />
        </svg>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute z-50 mt-1 w-full bg-bg-elevated border border-border rounded shadow-xl shadow-black/40 overflow-hidden"
          >
            <div className="p-2 border-b border-border">
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search branches..."
                className="w-full bg-black/30 border border-border rounded px-2.5 py-1.5 text-content text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40"
                onKeyDown={(e) => {
                  if (e.key === "Escape") { setOpen(false); setQuery(""); }
                  if (e.key === "Enter" && sorted.length > 0) {
                    onSelect(sorted[0]);
                    setOpen(false);
                    setQuery("");
                  }
                }}
              />
            </div>
            <div className="max-h-48 overflow-y-auto">
              {sorted.length === 0 ? (
                <div className="px-3 py-2 text-content text-text-secondary">No branches match</div>
              ) : (
                sorted.map((b) => (
                  <button
                    key={b}
                    onClick={() => { onSelect(b); setOpen(false); setQuery(""); }}
                    className={clsx(
                      "w-full flex items-center gap-2 px-3 py-1.5 text-left text-content font-mono transition-colors",
                      b === selected
                        ? "bg-[#00ff88]/[0.06] text-[#00ff88]"
                        : "text-text-secondary hover:bg-white/[0.03] hover:text-accent-hover"
                    )}
                  >
                    {b === selected ? (
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#00ff88" strokeWidth="1.5" className="shrink-0">
                        <polyline points="2 5 4 7 8 3" />
                      </svg>
                    ) : (
                      <span className="w-[10px]" />
                    )}
                    {b}
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
