"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";
import { Button } from "@/components/ui/Button";
import { ModelSelector } from "@/components/ui/ModelSelector";
import { CollapsibleSection } from "@/components/controls/CollapsibleSection";
import { clsx } from "clsx";
import { MODELS, loadStoredModel, capitalize, DEFAULT_BASE_BRANCH } from "@/lib/constants";
import type { ModelId } from "@/lib/constants";
import { fetchRepoEnv, saveRepoEnv, fetchRepoMounts, saveRepoMounts } from "@/lib/api";
import type { HostMount } from "@/lib/api";

export interface StartRunModalProps {
  open: boolean;
  onClose: () => void;
  onStart: (prompt: string | undefined, budget: number, durationMinutes: number, baseBranch: string, model: string, effort: string) => void;
  busy: boolean;
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

function countEnvVars(text: string): number {
  return text.split("\n").filter((line) => {
    const trimmed = line.trim();
    return trimmed && !trimmed.startsWith("#") && trimmed.includes("=");
  }).length;
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

const QUICK_START_ICONS: Record<string, React.ReactElement> = {
  sparkle: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 1v2M7 11v2M1 7h2M11 7h2M3.22 3.22l1.42 1.42M9.36 9.36l1.42 1.42M9.36 4.64L10.78 3.22M3.22 10.78l1.42-1.42" />
    </svg>
  ),
  shield: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 1.5L2 3.5v3c0 2.8 2.1 5.1 5 5.5 2.9-.4 5-2.7 5-5.5v-3L7 1.5z" />
      <polyline points="5 7 6.5 8.5 9 5.5" />
    </svg>
  ),
  flask: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 1h4M5 1v4.5L2 11c-.4.8.1 2 1.5 2h7c1.4 0 1.9-1.2 1.5-2L9 5.5V1" />
      <line x1="4" y1="9" x2="10" y2="9" />
    </svg>
  ),
  bug: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7" cy="8" r="3" />
      <path d="M7 5V2M4 8H1M10 8h3M4.5 5.5L2.5 3.5M9.5 5.5l2-2M4.5 10.5l-2 2M9.5 10.5l2 2" />
    </svg>
  ),
};

type QuickStartIcon = keyof typeof QUICK_START_ICONS;

const QUICK_PROMPTS: { label: string; icon: QuickStartIcon; prompt: string | undefined; desc: string }[] = [
  { label: "General improvement", icon: "sparkle", prompt: undefined, desc: "Default: security, bugs, tests, quality" },
  { label: "Security hardening", icon: "shield", prompt: "Focus on security: find and fix vulnerabilities, add input validation, review auth flows, check for injection risks.", desc: "Fix security issues" },
  { label: "Test coverage", icon: "flask", prompt: "Focus exclusively on adding test coverage. Find untested critical paths and write thorough tests for them.", desc: "Add missing tests" },
  { label: "Bug fixes", icon: "bug", prompt: "Focus on finding and fixing bugs: error handling gaps, edge cases, race conditions, incorrect logic. Run tests after each fix.", desc: "Find and fix bugs" },
];

export function StartRunModal({ open, onClose, onStart, busy, activeRepo }: StartRunModalProps) {
  const [customPrompt, setCustomPrompt] = useState("");
  const [budgetEnabled, setBudgetEnabled] = useState(false);
  const [budget, setBudget] = useState(50);
  const [duration, setDuration] = useState(0);
  const baseBranch = DEFAULT_BASE_BRANCH;
  const [selectedQuick, setSelectedQuick] = useState<number | null>(null);
  const [model, setModel] = useState<ModelId>(loadStoredModel);
  const [effort, setEffort] = useState<EffortLevel>("medium");
  const [envText, setEnvText] = useState("");
  const [envError, setEnvError] = useState<string | null>(null);
  const [mounts, setMounts] = useState<HostMount[]>([]);
  const [mountError, setMountError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open && activeRepo) {
      setEnvError(null);
      setMountError(null);
      fetchRepoEnv(activeRepo).then((env) => {
        setEnvText(Object.keys(env).length > 0 ? envToText(env) : "");
      }).catch(() => {
        setEnvError("Failed to load environment variables");
      });
      fetchRepoMounts(activeRepo).then(setMounts).catch(() => {
        setMountError("Failed to load host mounts");
      });
    }
  }, [open, activeRepo]);

  useEffect(() => {
    if (open) setTimeout(() => textareaRef.current?.focus(), 150);
  }, [open]);

  useEffect(() => {
    if (open) {
      const original = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = original; };
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const handleStart = async () => {
    const prompt = selectedQuick !== null ? QUICK_PROMPTS[selectedQuick].prompt : customPrompt.trim() || undefined;
    if (activeRepo) {
      try {
        await saveRepoEnv(activeRepo, parseEnvText(envText));
        setEnvError(null);
      } catch (e) {
        setEnvError(e instanceof Error ? e.message : "Failed to save env vars");
        return;
      }
      try {
        await saveRepoMounts(activeRepo, mounts);
        setMountError(null);
      } catch (e) {
        setMountError(e instanceof Error ? e.message : "Failed to save mounts");
        return;
      }
    }
    onStart(prompt, budgetEnabled ? budget : 0, duration, baseBranch, model, effort);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); handleStart(); }
  };

  const modelSummary = `${MODELS[model].label} · ${capitalize(effort)}`;
  const budgetSummary = budgetEnabled ? `$${budget}` : "Unlimited";
  const envCount = countEnvVars(envText);
  const envSummary = envCount > 0 ? `${envCount} vars` : "No vars";
  const mountSummary = mounts.length > 0 ? `${mounts.length} mount${mounts.length > 1 ? "s" : ""}` : "None";
  const selectedDurationPreset = DURATION_PRESETS.find((d) => d.minutes === duration);

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="modal-backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[9990] bg-black/70 frosted-glass"
            onClick={onClose}
          />
          <div className="fixed inset-0 z-[9991] flex items-center justify-center pointer-events-none">
            <motion.div
              key="modal-content"
              initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}
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
                    <h2 className="text-title font-semibold text-text">New Run</h2>
                    <p className="text-content text-text-muted mt-0.5">Spawns an isolated container with its own sandbox</p>
                  </div>
                </div>
                <button onClick={onClose} className="p-1 rounded hover:bg-white/[0.04] text-text-muted hover:text-accent-hover transition-colors focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-1 focus-visible:outline-[#00ff88]">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <line x1="3" y1="3" x2="9" y2="9" /><line x1="9" y1="3" x2="3" y2="9" />
                  </svg>
                </button>
              </div>

              <div className="p-5 space-y-4">
                {/* Quick prompts */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">Quick Start</label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {QUICK_PROMPTS.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => { setSelectedQuick(selectedQuick === i ? null : i); setCustomPrompt(""); }}
                        className={clsx(
                          "group text-left p-3 rounded border transition-all text-content hover:scale-[1.01]",
                          selectedQuick === i
                            ? "border-border border-l-2 border-l-[#00ff88] bg-[#00ff88]/[0.06]"
                            : "border-border bg-white/[0.01] hover:bg-white/[0.03]"
                        )}
                      >
                        <div className="flex items-center gap-1.5 font-medium text-accent-hover">
                          <span className="text-text-muted">{QUICK_START_ICONS[q.icon]}</span>
                          {q.label}
                        </div>
                        <div className="text-text-muted mt-0.5">{q.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="separator-subtle my-1" />

                {/* Custom prompt */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">Custom Prompt</label>
                  <textarea
                    ref={textareaRef}
                    value={customPrompt}
                    onChange={(e) => { setCustomPrompt(e.target.value); setSelectedQuick(null); }}
                    onKeyDown={handleKeyDown}
                    placeholder="e.g., Refactor the auth module to use JWT tokens instead of session cookies..."
                    rows={3}
                    className="mt-2 w-full bg-black/30 border border-border rounded px-3 py-2.5 text-content text-accent-hover placeholder:text-text-secondary resize-y focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
                  />
                </div>

                {/* Session Duration */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">Session Duration</label>
                  <div className="flex gap-1.5 flex-wrap mt-2">
                    {DURATION_PRESETS.map((d) => (
                      <button
                        key={d.minutes}
                        onClick={() => setDuration(d.minutes)}
                        className={clsx(
                          "text-content px-3 py-2 rounded border transition-all",
                          duration === d.minutes
                            ? "border-[#00ff88]/30 bg-[#00ff88]/[0.06] text-[#00ff88] font-medium"
                            : "border-border bg-white/[0.01] text-text-dim hover:bg-white/[0.03]"
                        )}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                  {selectedDurationPreset && duration > 0 && (
                    <p className="mt-2 text-xs text-white/40">{selectedDurationPreset.desc}</p>
                  )}
                </div>

                <div className="separator-subtle my-1" />

                {/* Model (collapsible) */}
                <CollapsibleSection label="Model" summary={modelSummary} defaultOpen={false}>
                  <div className="space-y-3">
                    <ModelSelector value={model} onChange={setModel} />
                    <div className="flex items-center justify-between">
                      <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">Thinking Effort</label>
                      <div className="flex items-center bg-black/30 border border-border rounded-full p-0.5">
                        {EFFORT_LEVELS.map((level) => (
                          <button
                            key={level}
                            type="button"
                            onClick={() => setEffort(level)}
                            className={clsx("px-2.5 py-0.5 rounded-full text-content capitalize transition-all", effort === level ? "bg-[#00ff88]/[0.12] text-[#00ff88] font-medium" : "text-text-dim hover:text-text-secondary")}
                          >
                            {level}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </CollapsibleSection>

                {/* Budget (collapsible) */}
                <CollapsibleSection label="Budget" summary={budgetSummary} defaultOpen={false}>
                  <div>
                    <label className="flex items-center gap-2 cursor-pointer select-none text-content text-text-secondary">
                      <input
                        type="checkbox"
                        checked={budgetEnabled}
                        onChange={() => setBudgetEnabled(!budgetEnabled)}
                        className="rounded"
                      />
                      Enable budget cap
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
                          className="flex-1 range-slider"
                        />
                        <span className="text-content font-semibold text-text tabular-nums w-16 text-right">${budget}</span>
                      </div>
                    )}
                  </div>
                </CollapsibleSection>

                {/* Environment Variables (collapsible) */}
                <CollapsibleSection label="Environment Variables" summary={envSummary} defaultOpen={false}>
                  <div>
                    <textarea
                      value={envText}
                      onChange={(e) => setEnvText(e.target.value)}
                      placeholder={"API_KEY=your-value\nDATABASE_URL=postgres://..."}
                      rows={3}
                      className="w-full bg-black/30 border border-border rounded px-3 py-2.5 text-content text-accent-hover font-mono placeholder:text-text-secondary resize-y focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <p className="mt-1 text-content text-text-secondary">KEY=value per line. Encrypted and injected into sandbox.</p>
                    {envError && <p className="mt-1 text-content text-[#ff4444]">{envError}</p>}
                  </div>
                </CollapsibleSection>

                {/* Host Mounts (collapsible) */}
                <CollapsibleSection label="Host Mounts" summary={mountSummary} defaultOpen={false}>
                  <div className="space-y-2">
                    <p className="text-content text-text-secondary mb-2">Repo is at /home/agentuser/repo inside the sandbox.</p>
                    {mounts.map((m, i) => (
                      <div key={i} className="space-y-1.5 mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-caption uppercase tracking-wider text-text-dim w-16 shrink-0">Host</span>
                          <input
                            type="text"
                            value={m.host_path}
                            onChange={(e) => {
                              const next = [...mounts];
                              next[i] = { ...m, host_path: e.target.value };
                              setMounts(next);
                            }}
                            placeholder="/Users/you/datasets"
                            className="flex-1 bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30"
                          />
                          <button
                            type="button"
                            onClick={() => setMounts(mounts.filter((_, j) => j !== i))}
                            className="p-1 text-text-dim hover:text-[#ff4444] transition-colors"
                          >
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <line x1="2" y1="2" x2="8" y2="8" /><line x1="8" y1="2" x2="2" y2="8" />
                            </svg>
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-caption uppercase tracking-wider text-text-dim w-16 shrink-0">Sandbox</span>
                          <input
                            type="text"
                            value={m.container_path}
                            onChange={(e) => {
                              const next = [...mounts];
                              next[i] = { ...m, container_path: e.target.value };
                              setMounts(next);
                            }}
                            placeholder="/home/agentuser/datasets"
                            className="flex-1 bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30"
                          />
                          <span className="w-[26px]" />
                        </div>
                        <div className="flex items-center gap-2 pl-[72px]">
                          <div className="flex items-center bg-black/30 border border-border rounded-full p-0.5">
                            {(["ro", "rw"] as const).map((mode) => (
                              <button
                                key={mode}
                                type="button"
                                onClick={() => {
                                  const next = [...mounts];
                                  next[i] = { ...m, mode };
                                  setMounts(next);
                                }}
                                className={clsx(
                                  "px-2.5 py-0.5 rounded-full text-content transition-all",
                                  m.mode === mode
                                    ? "bg-[#00ff88]/[0.12] text-[#00ff88] font-medium"
                                    : "text-text-dim hover:text-text-secondary"
                                )}
                              >
                                {mode === "ro" ? "Read only" : "Read & write"}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => setMounts([...mounts, { host_path: "", container_path: "", mode: "ro" }])}
                      className="text-content text-text-secondary hover:text-accent-hover transition-colors"
                    >
                      + Add mount
                    </button>
                    {mountError && <p className="mt-1 text-content text-[#ff4444]">{mountError}</p>}
                  </div>
                </CollapsibleSection>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between px-5 py-3 border-t border-border">
                <span className="text-content text-text-secondary">Ctrl+Enter to start</span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="md" onClick={onClose}>Cancel</Button>
                  <Button
                    variant="success" size="md" onClick={handleStart} disabled={busy}
                    icon={<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="3 2 8 5 3 8" /></svg>}
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
