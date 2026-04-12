"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";
import { Button } from "@/components/ui/Button";
import { ModelSelector } from "@/components/ui/ModelSelector";
import { clsx } from "clsx";
import { loadStoredModel } from "@/lib/constants";
import type { ModelId } from "@/lib/constants";
import { fetchRepoEnv, saveRepoEnv } from "@/lib/api";
import { BranchPicker } from "@/components/controls/BranchPicker";
import {
  DURATION_PRESETS,
  QUICK_PROMPTS,
  parseEnvText,
  envToText,
} from "@/lib/startRunPresets";

interface StartRunModalProps {
  open: boolean;
  onClose: () => void;
  onStart: (
    prompt: string | undefined,
    budget: number,
    durationMinutes: number,
    baseBranch: string,
    model: string
  ) => void;
  busy: boolean;
  branches: string[];
  activeRepo: string | null;
}

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
  const [envText, setEnvText] = useState("");
  const [envError, setEnvError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch saved env vars when modal opens
  useEffect(() => {
    if (open && activeRepo) {
      setEnvError(null);
      fetchRepoEnv(activeRepo)
        .then((env) => {
          setEnvText(Object.keys(env).length > 0 ? envToText(env) : "");
        })
        .catch(() => {
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
      return () => {
        document.body.style.overflow = original;
      };
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
        setEnvError(
          e instanceof Error ? e.message : "Failed to save env vars"
        );
        return;
      }
    }
    onStart(prompt, budgetEnabled ? budget : 0, duration, baseBranch, model);
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
          <div className="fixed inset-0 z-[9991] flex items-center justify-center pointer-events-none">
            <motion.div
              key="modal-content"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className="w-[520px] max-h-[80vh] overflow-y-auto bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg shadow-2xl shadow-black/60 card-accent-top pointer-events-auto"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-[#1a1a1a]">
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center justify-center h-7 w-7 rounded bg-white/[0.04] border border-white/[0.08]">
                    <Image src="/logo.svg" alt="AutoFyn" width={16} height={16} />
                  </div>
                  <div>
                    <h2 className="text-[12px] font-semibold text-[#e8e8e8]">
                      New Run
                    </h2>
                    <p className="text-[9px] text-[#999] mt-0.5">
                      Spawns an isolated container with its own sandbox
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="p-1 rounded hover:bg-white/[0.04] text-[#999] hover:text-[#aaa] transition-colors"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 12 12"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <line x1="3" y1="3" x2="9" y2="9" />
                    <line x1="9" y1="3" x2="3" y2="9" />
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
                  <label className="text-[10px] uppercase tracking-[0.15em] text-[#999] font-semibold">
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
                          "text-left p-3 rounded border transition-all",
                          selectedQuick === i
                            ? "border-[#00ff88]/30 bg-[#00ff88]/[0.04]"
                            : "border-[#1a1a1a] bg-white/[0.01] hover:bg-white/[0.03]"
                        )}
                      >
                        <div className="text-[10px] font-medium text-[#ccc]">
                          {q.label}
                        </div>
                        <div className="text-[9px] text-[#999] mt-0.5">
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
                  <label className="text-[10px] uppercase tracking-[0.15em] text-[#999] font-semibold">
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
                    className="mt-2 w-full bg-black/30 border border-[#1a1a1a] rounded px-3 py-2.5 text-[11px] text-[#ccc] placeholder-[#666] resize-y focus:outline-none focus:border-[#00ff88]/30 transition-all"
                  />
                </div>

                {/* Model Selector */}
                <div>
                  <label className="text-[10px] uppercase tracking-[0.15em] text-[#999] font-semibold">
                    Model
                  </label>
                  <div className="mt-2">
                    <ModelSelector value={model} onChange={setModel} />
                  </div>
                </div>

                {/* Duration lock */}
                <div>
                  <label className="text-[10px] uppercase tracking-[0.15em] text-[#999] font-semibold">
                    Session Duration
                  </label>
                  <p className="text-[10px] text-[#888] mt-0.5 mb-2">
                    Agent cannot call end_session until this time expires
                  </p>
                  <div className="flex gap-1.5 flex-wrap">
                    {DURATION_PRESETS.map((d) => (
                      <button
                        key={d.minutes}
                        onClick={() => setDuration(d.minutes)}
                        className={clsx(
                          "text-[9px] px-2 py-1.5 rounded border transition-all",
                          duration === d.minutes
                            ? "border-[#00ff88]/30 bg-[#00ff88]/[0.06] text-[#00ff88]"
                            : "border-[#1a1a1a] bg-white/[0.01] text-[#777] hover:bg-white/[0.03]"
                        )}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Environment Variables */}
                <div>
                  <label className="text-[10px] uppercase tracking-[0.15em] text-[#999] font-semibold">
                    Environment Variables
                  </label>
                  <textarea
                    value={envText}
                    onChange={(e) => setEnvText(e.target.value)}
                    placeholder={"API_KEY=your-value\nDATABASE_URL=postgres://..."}
                    rows={3}
                    className="mt-2 w-full bg-black/30 border border-[#1a1a1a] rounded px-3 py-2.5 text-[11px] text-[#ccc] font-mono placeholder-[#555] resize-y focus:outline-none focus:border-[#00ff88]/30 transition-all"
                    autoComplete="off"
                    spellCheck={false}
                  />
                  <p className="mt-1 text-[9px] text-[#666]">
                    KEY=value per line. Encrypted and injected into sandbox.
                  </p>
                  {envError && (
                    <p className="mt-1 text-[9px] text-[#ff4444]">{envError}</p>
                  )}
                </div>

                {/* Budget */}
                <div>
                  <label
                    className="text-[10px] uppercase tracking-[0.15em] text-[#999] font-semibold flex items-center gap-2 cursor-pointer select-none"
                    onClick={() => setBudgetEnabled(!budgetEnabled)}
                  >
                    <span
                      className={clsx(
                        "flex items-center justify-center h-3 w-3 rounded border transition-all",
                        budgetEnabled
                          ? "bg-[#00ff88] border-[#00ff88]"
                          : "border-[#666] bg-transparent"
                      )}
                    >
                      {budgetEnabled && (
                        <svg
                          width="8"
                          height="8"
                          viewBox="0 0 8 8"
                          fill="none"
                          stroke="white"
                          strokeWidth="1.5"
                        >
                          <polyline points="1.5 4 3 5.5 6.5 2" />
                        </svg>
                      )}
                    </span>
                    Max Budget
                    {!budgetEnabled && (
                      <span className="text-[10px] text-[#888] font-normal normal-case tracking-normal ml-1">
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
                      <span className="text-[12px] font-semibold text-[#e8e8e8] tabular-nums w-16 text-right">
                        ${budget}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between px-5 py-3 border-t border-[#1a1a1a]">
                <span className="text-[9px] text-[#888]">Ctrl+Enter to start</span>
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
                      <svg
                        width="10"
                        height="10"
                        viewBox="0 0 10 10"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      >
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
