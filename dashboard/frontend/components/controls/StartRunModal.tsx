"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";
import { Button } from "@/components/ui/Button";
import { ModelSelector } from "@/components/ui/ModelSelector";
import { CollapsibleSection } from "@/components/controls/CollapsibleSection";
import { BranchPicker } from "@/components/controls/BranchPicker";
import { HostMountsEditor } from "@/components/controls/HostMountsEditor";
import { SandboxPicker } from "@/components/controls/SandboxPicker";
import { McpServersEditor } from "@/components/controls/McpServersEditor";
import { clsx } from "clsx";
import { MODELS, loadStoredModel, capitalize, DEFAULT_BASE_BRANCH, DEFAULT_DOCKER_START_CMD, STARTER_PRESETS, STARTER_PRESET_KEYS, EFFORT_LEVELS, DEFAULT_EFFORT } from "@/lib/constants";
import type { StarterPresetKey, EffortLevel, ModelId } from "@/lib/constants";
import { fetchRepoEnv, saveRepoEnv, fetchRepoMounts, saveRepoMounts, fetchRemoteMounts, saveRemoteMounts, fetchRepoMcpServers, saveRepoMcpServers, fetchRemoteSandboxes, updateRemoteSandbox, fetchLastStartCmd } from "@/lib/api";
import type { HostMount, RemoteSandboxConfig } from "@/lib/api";

export interface StartRunModalProps {
  open: boolean;
  onClose: () => void;
  onStart: (prompt: string | undefined, preset: string | undefined, budget: number, durationMinutes: number, baseBranch: string, model: string, effort: string, sandboxId: string | null, startCmd: string) => void;
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

function countEnvVars(text: string): number {
  return text.split("\n").filter((line) => {
    const trimmed = line.trim();
    return trimmed && !trimmed.startsWith("#") && trimmed.includes("=");
  }).length;
}

function envToText(env: Record<string, string>): string {
  return Object.entries(env).map(([k, v]) => `${k}=${v}`).join("\n");
}

const PROMPT_LINE_HEIGHT = 24;
const PROMPT_VERTICAL_PADDING = 20;
const PROMPT_MIN_ROWS = 3;
const PROMPT_MAX_ROWS = 10;

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

export function StartRunModal({ open, onClose, onStart, busy, branches, activeRepo }: StartRunModalProps) {
  const [customPrompt, setCustomPrompt] = useState("");
  const [budget, setBudget] = useState(0);
  const [duration, setDuration] = useState(0);
  const [baseBranch, setBaseBranch] = useState(DEFAULT_BASE_BRANCH);
  const [selectedQuick, setSelectedQuick] = useState<StarterPresetKey | null>(null);
  const [model, setModel] = useState<ModelId>(loadStoredModel);
  const [effort, setEffort] = useState<EffortLevel>(DEFAULT_EFFORT);
  const [envText, setEnvText] = useState("");
  const [envError, setEnvError] = useState<string | null>(null);
  const [mounts, setMounts] = useState<HostMount[]>([]);
  const [mountError, setMountError] = useState<string | null>(null);
  const [mountsLoading, setMountsLoading] = useState(false);
  const [mcpText, setMcpText] = useState("");
  const [mcpError, setMcpError] = useState<string | null>(null);
  const [remoteSandboxes, setRemoteSandboxes] = useState<RemoteSandboxConfig[]>([]);
  const [selectedSandboxId, setSelectedSandboxId] = useState<string | null>(null);
  const [startCmd, setStartCmd] = useState(DEFAULT_DOCKER_START_CMD);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prevOpenRef = useRef(open);

  const adjustPromptHeight = useCallback((): void => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = PROMPT_MAX_ROWS * PROMPT_LINE_HEIGHT + PROMPT_VERTICAL_PADDING;
    const minHeight = PROMPT_MIN_ROWS * PROMPT_LINE_HEIGHT + PROMPT_VERTICAL_PADDING;
    const clamped = Math.min(Math.max(el.scrollHeight, minHeight), maxHeight);
    el.style.height = `${clamped}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, []);

  const loadMountsForSandbox = useCallback(async (sandboxId: string | null): Promise<void> => {
    if (!activeRepo) { setMounts([]); return; }
    setMountsLoading(true);
    setMountError(null);
    try {
      const loaded = sandboxId === null
        ? await fetchRepoMounts(activeRepo)
        : await fetchRemoteMounts(activeRepo, sandboxId);
      setMounts(loaded);
    } catch (e) {
      setMountError(e instanceof Error ? e.message : "Failed to load mounts");
      setMounts([]);
    } finally {
      setMountsLoading(false);
    }
  }, [activeRepo]);

  // Reset all local form state when modal transitions from closed to open.
  // This ensures a fresh form each time the user opens the modal, regardless
  // of how it was left during a previous session.
  useEffect(() => {
    const wasOpen = prevOpenRef.current;
    prevOpenRef.current = open;
    if (!wasOpen && open) {
      setCustomPrompt("");
      setBudget(0);
      setDuration(0);
      setBaseBranch(DEFAULT_BASE_BRANCH);
      setSelectedQuick(null);
      setEffort(DEFAULT_EFFORT);
      setEnvText("");
      setMounts([]);
      setMcpText("");
      setStartCmd(DEFAULT_DOCKER_START_CMD);
      setSelectedSandboxId(null);
      submittingRef.current = false;
      setSubmitting(false);
      setEnvError(null);
      setMountError(null);
      setMcpError(null);
      setMountsLoading(false);
      // Load local-Docker mounts immediately on open. If a remote sandbox is
      // restored asynchronously (restoration effect), it will overwrite these
      // with remote mounts for the correct sandbox.
      if (activeRepo) void loadMountsForSandbox(null);
    }
  }, [open, activeRepo, loadMountsForSandbox]);

  // Restore last-used sandbox and its start command per repo.
  // Runs when remoteSandboxes loads (async), which has the latest
  // default_start_cmd from the database — even if user just changed it
  // in Settings.
  useEffect(() => {
    if (!open || !activeRepo || remoteSandboxes.length === 0) return;
    try {
      const saved = localStorage.getItem(`autofyn_last_sandbox:${activeRepo}`);
      if (!saved) return;
      const sandbox = remoteSandboxes.find((s) => s.id === saved);
      if (!sandbox) {
        // Sandbox was deleted — clear stale selection.
        localStorage.removeItem(`autofyn_last_sandbox:${activeRepo}`);
        return;
      }
      setSelectedSandboxId(saved);
      void loadMountsForSandbox(saved);
      fetchLastStartCmd(saved, activeRepo)
        .catch(() => null)
        .then((lastCmd) => setStartCmd(lastCmd || sandbox.default_start_cmd));
    } catch (e) { console.warn("Failed to restore last sandbox selection", e); }
  }, [open, activeRepo, remoteSandboxes, loadMountsForSandbox]);

  useEffect(() => { adjustPromptHeight(); }, [customPrompt, adjustPromptHeight]);

  useEffect(() => {
    if (open) fetchRemoteSandboxes().then(setRemoteSandboxes).catch(() => setRemoteSandboxes([]));
  }, [open]);

  useEffect(() => {
    if (open && activeRepo) {
      setEnvError(null);
      setMcpError(null);
      fetchRepoEnv(activeRepo).then((env) => {
        setEnvText(Object.keys(env).length > 0 ? envToText(env) : "");
      }).catch(() => setEnvError("Failed to load environment variables"));
      fetchRepoMcpServers(activeRepo).then((servers) => {
        setMcpText(Object.keys(servers).length > 0 ? JSON.stringify(servers, null, 2) : "");
      }).catch(() => setMcpError("Failed to load MCP servers"));
    }
  }, [open, activeRepo]);

  useEffect(() => { if (open) setTimeout(() => textareaRef.current?.focus(), 150); }, [open]);

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

  const handleSandboxSelect = useCallback((id: string | null) => {
    setSelectedSandboxId(id);
    loadMountsForSandbox(id);
    if (activeRepo) {
      try {
        if (id) localStorage.setItem(`autofyn_last_sandbox:${activeRepo}`, id);
        else localStorage.removeItem(`autofyn_last_sandbox:${activeRepo}`);
      } catch (e) { console.warn("Failed to persist sandbox selection to localStorage", e); }
    }
  }, [loadMountsForSandbox, activeRepo]);

  const handleStart = async (): Promise<void> => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    try {
      const prompt = selectedQuick !== null ? undefined : customPrompt.trim() || undefined;
      const preset = selectedQuick !== null ? selectedQuick : undefined;
      const hasMcpServers = mcpText.trim().length > 0;
      if (!activeRepo && (countEnvVars(envText) > 0 || mounts.length > 0 || hasMcpServers)) {
        setEnvError("Select a repository before configuring environment variables, host mounts, or MCP servers");
        return;
      }
      if (activeRepo) {
        try { await saveRepoEnv(activeRepo, parseEnvText(envText)); setEnvError(null); }
        catch (e) { setEnvError(e instanceof Error ? e.message : "Failed to save env vars"); return; }
        try {
          if (selectedSandboxId === null) await saveRepoMounts(activeRepo, mounts);
          else await saveRemoteMounts(activeRepo, selectedSandboxId, mounts);
          setMountError(null);
        } catch (e) { setMountError(e instanceof Error ? e.message : "Failed to save mounts"); return; }
        try {
          const parsedMcp: unknown = mcpText.trim() ? JSON.parse(mcpText) : {};
          if (typeof parsedMcp !== "object" || parsedMcp === null || Array.isArray(parsedMcp)) {
            setMcpError("MCP servers must be a JSON object"); return;
          }
          await saveRepoMcpServers(activeRepo, parsedMcp as Record<string, Record<string, unknown>>);
          setMcpError(null);
        } catch (e) { setMcpError(e instanceof Error ? e.message : "Failed to save MCP servers"); return; }
      }
      const cmdToSend = startCmd.trim();
      if (selectedSandboxId !== null && cmdToSend) {
        const sandbox = remoteSandboxes.find((s) => s.id === selectedSandboxId);
        if (sandbox && cmdToSend !== sandbox.default_start_cmd) {
          void updateRemoteSandbox(selectedSandboxId, { ...sandbox, default_start_cmd: cmdToSend });
        }
      }
      onStart(prompt, preset, budget, duration, baseBranch, model, effort, selectedSandboxId, cmdToSend);
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (submittingRef.current || busy) return;
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void handleStart(); }
  };

  const modelSummary = `${MODELS[model].label} · ${capitalize(effort)}`;
  const budgetSummary = budget > 0 ? `$${budget}` : "Unlimited";
  const envCount = countEnvVars(envText);
  const envSummary = envCount > 0 ? `${envCount} vars` : "No vars";
  const mountSummary = mountsLoading ? "Loading..." : (mounts.length > 0 ? `${mounts.length} mount${mounts.length > 1 ? "s" : ""}` : "None");
  const mcpSummary = mcpText.trim() ? "Configured" : "None";
  const sandboxSummary = selectedSandboxId === null
    ? "Docker (local)"
    : remoteSandboxes.find((s) => s.id === selectedSandboxId)?.name ?? "Remote";
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
                <BranchPicker branches={branches} selected={baseBranch} onSelect={setBaseBranch} />

                {/* Quick prompts */}
                <div>
                  <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold">Quick Start</label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {STARTER_PRESET_KEYS.map((key) => {
                      const p = STARTER_PRESETS[key];
                      return (
                        <button
                          key={key}
                          onClick={() => { setSelectedQuick(selectedQuick === key ? null : key); setCustomPrompt(""); }}
                          className={clsx(
                            "group text-left p-3 rounded border transition-all text-content hover:scale-[1.01]",
                            selectedQuick === key
                              ? "border-border border-l-2 border-l-[#00ff88] bg-[#00ff88]/[0.06]"
                              : "border-border bg-white/[0.01] hover:bg-white/[0.03]"
                          )}
                        >
                          <div className="flex items-center gap-1.5 font-medium text-accent-hover">
                            <span className="text-text-muted">{QUICK_START_ICONS[p.icon]}</span>
                            {p.label}
                          </div>
                          <div className="text-text-muted mt-0.5">{p.desc}</div>
                        </button>
                      );
                    })}
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
                    placeholder="e.g., Optimize the algorithm to hit 60% compression ratio without further quality loss..."
                    rows={PROMPT_MIN_ROWS}
                    className="mt-2 w-full bg-black/30 border border-border rounded px-3 py-2.5 text-content text-accent-hover placeholder:text-text-secondary resize-none leading-6 transition-[height] duration-100 focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40"
                    style={{ minHeight: `${PROMPT_MIN_ROWS * PROMPT_LINE_HEIGHT + PROMPT_VERTICAL_PADDING}px` }}
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
                  <div className="flex items-center gap-3">
                    <input type="range" min={0} max={1000} step={5} value={budget} onChange={(e) => setBudget(Number(e.target.value))} className="flex-1 range-slider" />
                    <span className="text-content font-semibold text-text tabular-nums w-20 text-right">
                      {budget === 0 ? "Unlimited" : `$${budget}`}
                    </span>
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

                {/* Sandbox picker (collapsible) */}
                <CollapsibleSection label="Sandbox" summary={sandboxSummary} defaultOpen={false}>
                  <SandboxPicker
                    sandboxes={remoteSandboxes}
                    selectedId={selectedSandboxId}
                    onSelect={handleSandboxSelect}
                    startCmd={startCmd}
                    onStartCmdChange={setStartCmd}
                    activeRepo={activeRepo}
                  />
                </CollapsibleSection>

                {/* Host Mounts (collapsible) */}
                <CollapsibleSection label="Host Mounts" summary={mountSummary} defaultOpen={false}>
                  <HostMountsEditor mounts={mounts} onChange={setMounts} loading={mountsLoading} error={mountError} isRemote={selectedSandboxId !== null} />
                </CollapsibleSection>

                {/* MCP Servers (collapsible) */}
                <CollapsibleSection label="MCP Servers" summary={mcpSummary} defaultOpen={false}>
                  <McpServersEditor value={mcpText} onChange={setMcpText} />
                  {mcpError && <p className="mt-1 text-content text-[#ff4444]">{mcpError}</p>}
                </CollapsibleSection>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between px-5 py-3 border-t border-border">
                <span className="text-content text-text-secondary">Ctrl+Enter to start</span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="md" onClick={onClose}>Cancel</Button>
                  <Button
                    variant="success" size="md" onClick={() => void handleStart()} disabled={busy || submitting}
                    icon={<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="3 2 8 5 3 8" /></svg>}
                  >
                    {busy || submitting ? "Starting..." : "New Run"}
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
