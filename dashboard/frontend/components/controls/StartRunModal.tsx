"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";
import { Button } from "@/components/ui/Button";
import { ModelSelector } from "@/components/ui/ModelSelector";
import { clsx } from "clsx";
import { PINNED_BRANCHES, loadStoredModel } from "@/lib/constants";
import type { ModelId } from "@/lib/constants";
import { fetchRepoEnv, saveRepoEnv } from "@/lib/api";

function BranchPicker({
  branches,
  selected,
  onSelect,
}: {
  branches: string[];
  selected: string;
  onSelect: (b: string) => void;
}) {
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

interface StartRunModalProps {
  open: boolean;
  onClose: () => void;
  onStart: (prompt: string | undefined, budget: number, durationMinutes: number, baseBranch: string, model: string, effort: string) => void;
  busy: boolean;
  branches: string[];
  activeRepo: string | null;
}

function parseEnvText(text: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const eqIdx = trimmed.indexOf("=");
    const key = trimmed.slice(0, eqIdx).trim();
    if (key) result[key] = trimmed.slice(eqIdx + 1);
  }
  return result;
}

function envToText(env: Record<string, string>): string {
  return Object.entries(env).map(([k, v]) => `${k}=${v}`).join("\n");
}

const EFFORT_LEVELS = ["low", "medium", "high", "max"] as const;
type EffortLevel = typeof EFFORT_LEVELS[number];

const DURATION_PRESETS = [
  { label: "No lock", minutes: 0, desc: "Agent can end anytime" },
  { label: "30 min", minutes: 30, desc: "Quick pass" },
  { label: "1 hour", minutes: 60, desc: "Focused session" },
  { label: "2 hours", minutes: 120, desc: "Deep dive" },
  { label: "4 hours", minutes: 240, desc: "Extended run" },
  { label: "8 hours", minutes: 480, desc: "Overnight" },
];

const QUICK_PROMPTS = [
  {
    label: "General improvement",
    prompt: undefined as string | undefined,
    desc: "Default: security, bugs, tests, quality",
  },
  {
    label: "Security hardening",
    prompt:
      "Focus on security: find and fix vulnerabilities, add input validation, review auth flows, check for injection risks.",
    desc: "Fix security issues",
  },
  {
    label: "Test coverage",
    prompt:
      "Focus exclusively on adding test coverage. Find untested critical paths and write thorough tests for them.",
    desc: "Add missing tests",
  },
  {
    label: "Bug fixes",
    prompt:
      "Focus on finding and fixing bugs: error handling gaps, edge cases, race conditions, incorrect logic. Run tests after each fix.",
    desc: "Find and fix bugs",
  },
];

export function StartRunModal({
  open,
  onClose,
  onStart,
  busy,
  branches,
  activeRepo,
}: StartRunModalProps) {
  const [customPrompt, setCustomPrompt] = useState("");
  const [budgetEnabled, setBudgetEnabled] = useState(false);
  const [budget, setBudget] = useState(50);
  const [duration, setDuration] = useState(0);
  const [baseBranch, setBaseBranch] = useState("main");
  const [selectedQuick, setSelectedQuick] = useState<number | null>(null);
  const [model, setModel] = useState<ModelId>(loadStoredModel);
  const [effort, setEffort] = useState<EffortLevel>("medium");
  const [envText, setEnvText] = useState("");
  const [envError, setEnvError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch saved env vars when modal opens
  useEffect(() => {
    if (open && activeRepo) {
      setEnvError(null);
      fetchRepoEnv(activeRepo).then((env) => {
        setEnvText(Object.keys(env).length > 0 ? envToText(env) : "");
      }).catch(() => {
        setEnvError("Failed to load environment variables");
      });
    }
  }, [open, activeRepo]);

  useEffect(() => {
    if (open) setTimeout(() => textareaRef.current?.focus(), 150);
  }, [open]);

  // Lock body scroll when open — save and restore original value
  useEffect(() => {
    if (open) {
      const original = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = original; };
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const handleStart = async () => {
    const prompt =
      selectedQuick !== null
        ? QUICK_PROMPTS[selectedQuick].prompt
        : customPrompt.trim() || undefined;
    if (activeRepo) {
      try {
        await saveRepoEnv(activeRepo, parseEnvText(envText));
        setEnvError(null);
      } catch (e) {
        setEnvError(e instanceof Error ? e.message : "Failed to save env vars");
        return;
      }
    }
    onStart(prompt, budgetEnabled ? budget : 0, duration, baseBranch, model, effort);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleStart();
    }
  };

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[9990] bg-black/70 frosted-glass"
            onClick={onClose}
          />

          {/* Centering wrapper — uses flexbox, no transforms */}
          <div
            className="fixed inset-0 z-[9991] flex items-center justify-center pointer-events-none"
          >
            <motion.div
              key="modal-content"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className="w-[520px] max-h-[80vh] overflow-y-auto bg-bg-card border border-border rounded-lg shadow-2xl shadow-black/60 card-accent-top pointer-events-auto"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center justify-center h-7 w-7 rounded bg-white/[0.04] border border-white/[0.08]">
                    <Image src="/logo.svg" alt="AutoFyn" width={16} height={16} />
                  </div>
                  <div>
                    <h2 className="text-title font-semibold text-text">
                      New Run
                    </h2>
                    <p className="text-content text-text-muted mt-0.5">
                      Spawns an isolated container with its own sandbox
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="p-1 rounded hover:bg-white/[0.04] text-text-muted hover:text-accent-hover transition-colors focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-1 focus-visible:outline-[#00ff88]"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <line x1="3" y1="3" x2="9" y2="9" /><line x1="9" y1="3" x2="3" y2="9" />
                  </svg>
                </button>
              </div>

              <div className="p-5 space-y-5">
                <BranchPicker
                  branches={branches}
                  selected={baseBranch}
                  onSelect={setBaseBranch}
                />

                {/* Quick prompts */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">
                    Quick Start
                  </label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {QUICK_PROMPTS.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setSelectedQuick(selectedQuick === i ? null : i);
                          setCustomPrompt("");
                        }}
                        className={clsx(
                          "text-left p-3 rounded border transition-all text-content",
                          selectedQuick === i
                            ? "border-[#00ff88]/30 bg-[#00ff88]/[0.04]"
                            : "border-border bg-white/[0.01] hover:bg-white/[0.03]"
                        )}
                      >
                        <div className="font-medium text-accent-hover">
                          {q.label}
                        </div>
                        <div className="text-text-muted mt-0.5">
                          {q.desc}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Divider */}
                <div className="separator-subtle" />

                {/* Custom prompt */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">
                    Custom Prompt
                  </label>
                  <textarea
                    ref={textareaRef}
                    value={customPrompt}
                    onChange={(e) => {
                      setCustomPrompt(e.target.value);
                      setSelectedQuick(null);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe what the agent should focus on..."
                    rows={3}
                    className="mt-2 w-full bg-black/30 border border-border rounded px-3 py-2.5 text-content text-accent-hover placeholder:text-text-secondary resize-y focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
                  />
                </div>

                {/* Model Selector */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">
                    Model
                  </label>
                  <div className="mt-2">
                    <ModelSelector value={model} onChange={setModel} />
                  </div>
                </div>

                {/* Thinking Effort */}
                <div className="flex items-center justify-between">
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">
                    Effort
                    <span className="normal-case tracking-normal font-normal ml-1.5 text-text-secondary">
                      ({effort})
                    </span>
                  </label>
                  <div className="flex items-center bg-black/30 border border-border rounded-full p-0.5">
                    {EFFORT_LEVELS.map((level) => (
                      <button
                        key={level}
                        onClick={() => setEffort(level)}
                        className={clsx(
                          "px-2.5 py-0.5 rounded-full text-content capitalize transition-all",
                          effort === level
                            ? "bg-[#00ff88]/[0.12] text-[#00ff88] font-medium"
                            : "text-text-dim hover:text-text-secondary"
                        )}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Duration lock */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">
                    Session Duration
                  </label>
                  <p className="text-content text-text-secondary mt-0.5 mb-2">
                    Agent cannot call end_session until this time expires
                  </p>
                  <div className="flex gap-1.5 flex-wrap">
                    {DURATION_PRESETS.map((d) => (
                      <button
                        key={d.minutes}
                        onClick={() => setDuration(d.minutes)}
                        className={clsx(
                          "text-content px-2 py-1.5 rounded border transition-all",
                          duration === d.minutes
                            ? "border-[#00ff88]/30 bg-[#00ff88]/[0.06] text-[#00ff88]"
                            : "border-border bg-white/[0.01] text-text-dim hover:bg-white/[0.03]"
                        )}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Environment Variables */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">
                    Environment Variables
                  </label>
                  <textarea
                    value={envText}
                    onChange={(e) => setEnvText(e.target.value)}
                    placeholder={"API_KEY=your-value\nDATABASE_URL=postgres://..."}
                    rows={3}
                    className="mt-2 w-full bg-black/30 border border-border rounded px-3 py-2.5 text-content text-accent-hover font-mono placeholder:text-text-secondary resize-y focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
                    autoComplete="off"
                    spellCheck={false}
                  />
                  <p className="mt-1 text-content text-text-secondary">
                    KEY=value per line. Encrypted and injected into sandbox.
                  </p>
                  {envError && <p className="mt-1 text-content text-[#ff4444]">{envError}</p>}
                </div>

                {/* Budget */}
                <div>
                  <label
                    className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold flex items-center gap-2 cursor-pointer select-none"
                    onClick={() => setBudgetEnabled(!budgetEnabled)}
                  >
                    <span
                      className={clsx(
                        "flex items-center justify-center h-3 w-3 rounded border transition-all",
                        budgetEnabled
                          ? "bg-[#00ff88] border-[#00ff88]"
                          : "border-border-faint bg-transparent"
                      )}
                    >
                      {budgetEnabled && (
                        <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="white" strokeWidth="1.5">
                          <polyline points="1.5 4 3 5.5 6.5 2" />
                        </svg>
                      )}
                    </span>
                    Max Budget
                    {!budgetEnabled && (
                      <span className="text-text-secondary font-normal normal-case tracking-normal ml-1">
                        (unlimited)
                      </span>
                    )}
                  </label>
                  {budgetEnabled && (
                    <div className="flex items-center gap-3 mt-2">
                      <input
                        type="range"
                        min={5}
                        max={200}
                        step={5}
                        value={budget}
                        onChange={(e) => setBudget(Number(e.target.value))}
                        className="flex-1 accent-[#00ff88]"
                      />
                      <span className="text-content font-semibold text-text tabular-nums w-16 text-right">
                        ${budget}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between px-5 py-3 border-t border-border">
                <span className="text-content text-text-secondary">
                  Ctrl+Enter to start
                </span>
                <div className="flex gap-2">
                  <Button variant="ghost" onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    variant="success"
                    size="md"
                    onClick={handleStart}
                    disabled={busy}
                    icon={
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <polygon points="3 2 8 5 3 8" />
                      </svg>
                    }
                  >
                    {busy ? "Starting..." : "New Run"}
                  </Button>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}
