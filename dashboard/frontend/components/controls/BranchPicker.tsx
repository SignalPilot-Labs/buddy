"use client";

import { useState, useRef, useEffect } from "react";
import { clsx } from "clsx";
import { useTranslation } from "@/hooks/useTranslation";

export interface BranchPickerProps {
  branches: string[];
  selected: string;
  onSelect: (b: string) => void;
}

export function BranchPicker({ branches, selected, onSelect }: BranchPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = query
    ? branches.filter((b) => b.toLowerCase().includes(query.toLowerCase()))
    : branches;

  const sorted = [...filtered].sort((a, b) => {
    const pinned = ["main", "staging"];
    const aPin = pinned.indexOf(a);
    const bPin = pinned.indexOf(b);
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
      <label className="text-[10px] uppercase tracking-[0.15em] text-[#999] font-semibold">
        {t.startRunModal.branchFrom}
      </label>
      <button
        onClick={() => setOpen(!open)}
        className="mt-1.5 w-full flex items-center justify-between px-3 py-2 bg-black/30 border border-[#1a1a1a] rounded text-[11px] text-left hover:border-[#2a2a2a] transition-colors"
      >
        <span className="font-mono text-[#e8e8e8]">{selected}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#999" strokeWidth="1.5" strokeLinecap="round">
          <polyline points="2 4 5 6 8 4" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-[#0d0d0d] border border-[#1a1a1a] rounded shadow-xl shadow-black/40 overflow-hidden">
          <div className="p-2 border-b border-[#1a1a1a]">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.startRunModal.searchBranches}
              className="w-full bg-black/30 border border-[#1a1a1a] rounded px-2.5 py-1.5 text-[10px] text-[#ccc] placeholder-[#666] focus:outline-none focus:border-[#00ff88]/30"
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
              <div className="px-3 py-2 text-[9px] text-[#888]">{t.startRunModal.noBranchesMatch}</div>
            ) : (
              sorted.map((b) => (
                <button
                  key={b}
                  onClick={() => { onSelect(b); setOpen(false); setQuery(""); }}
                  className={clsx(
                    "w-full flex items-center gap-2 px-3 py-1.5 text-left text-[10px] font-mono transition-colors",
                    b === selected
                      ? "bg-[#00ff88]/[0.06] text-[#00ff88]"
                      : "text-[#888] hover:bg-white/[0.03] hover:text-[#ccc]"
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
        </div>
      )}
    </div>
  );
}
