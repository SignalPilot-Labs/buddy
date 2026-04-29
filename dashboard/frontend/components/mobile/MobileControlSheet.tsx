"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RunStatus, RepoInfo } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { RepoSelector } from "@/components/ui/RepoSelector";
import { ACTIVE_STATUSES } from "@/lib/constants";

interface MobileControlSheetProps {
  open: boolean;
  onClose: () => void;
  // Run controls
  status: RunStatus | null;
  onStop: () => void;
  onUnlock: () => void;
  busy: boolean;
  // Repo
  repos: RepoInfo[];
  activeRepo: string | null;
  onRepoSelect: (repo: string) => void;
  // New run
  onNewRun: () => void;
  isConfigured: boolean;
}

export function MobileControlSheet({
  open,
  onClose,
  status,
  onStop,
  onUnlock,
  busy,
  repos,
  activeRepo,
  onRepoSelect,
  onNewRun,
  isConfigured,
}: MobileControlSheetProps) {
  const s = status ?? ("" as never);
  const isActive = ACTIVE_STATUSES.includes(s);

  // Lock body scroll when open — save and restore original value
  useEffect(() => {
    if (open) {
      const original = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = original; };
    }
  }, [open]);

  // Close on ESC key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[60] bg-black/60"
            onClick={onClose}
          />

          {/* Sheet */}
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 400 }}
            className="fixed bottom-0 left-0 right-0 z-[61] bg-bg-card border-t border-border rounded-t-2xl safe-area-bottom"
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-8 h-1 rounded-full bg-border-subtle" />
            </div>

            <div className="px-4 pb-6 space-y-4">
              {/* Repo selector */}
              <div>
                <label className="text-content uppercase tracking-[0.15em] text-text-secondary font-semibold mb-2 block">
                  Repository
                </label>
                <RepoSelector
                  repos={repos}
                  activeRepo={activeRepo}
                  onSelect={(repo) => { onRepoSelect(repo); onClose(); }}
                  // 280px accounts for: drag handle (~20px), label (~28px), new run button (~44px),
                  // run controls section (~100px), padding (~60px), safe area
                  dropdownMaxHeight="max-h-[calc(100vh-280px)]"
                />
              </div>

              {/* New Run */}
              <Button
                variant="success"
                size="md"
                onClick={() => { onNewRun(); onClose(); }}
                disabled={!isConfigured}
                className="w-full justify-center"
                icon={
                  <svg width="12" height="12" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <polygon points="3 2 8 5 3 8" />
                  </svg>
                }
              >
                {isConfigured ? "New Run" : "Setup Required"}
              </Button>

              {/* Run controls */}
              {status && isActive && (
                <>
                  <label className="text-content uppercase tracking-[0.15em] text-text-secondary font-semibold block">
                    Run Controls
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      variant="danger"
                      size="md"
                      disabled={!isActive || busy}
                      onClick={() => { onStop(); onClose(); }}
                      className="justify-center"
                      icon={
                        <svg width="12" height="12" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <rect x="2" y="2" width="6" height="6" rx="0.5" />
                        </svg>
                      }
                    >
                      Stop
                    </Button>
                    <Button
                      variant="warning"
                      size="md"
                      disabled={!isActive || busy}
                      onClick={() => { onUnlock(); onClose(); }}
                      className="justify-center"
                      icon={
                        <svg width="12" height="12" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <rect x="2" y="5" width="6" height="4" rx="0.5" />
                          <path d="M3.5 5V3.5a1.5 1.5 0 013 0" />
                        </svg>
                      }
                    >
                      Unlock
                    </Button>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
