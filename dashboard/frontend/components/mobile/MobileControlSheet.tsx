"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RunStatus, RepoInfo } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { RepoSelector } from "@/components/ui/RepoSelector";

interface MobileControlSheetProps {
  open: boolean;
  onClose: () => void;
  status: RunStatus | null;
  onPause: () => void;
  onOpenInject: () => void;
  busy: boolean;
  repos: RepoInfo[];
  activeRepo: string | null;
  onRepoSelect: (repo: string) => void;
  onNewRun: () => void;
  isConfigured: boolean;
}

export function MobileControlSheet({
  open,
  onClose,
  status,
  onPause,
  onOpenInject,
  busy,
  repos,
  activeRepo,
  onRepoSelect,
  onNewRun,
  isConfigured,
}: MobileControlSheetProps) {
  // Lock body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = ""; };
    }
  }, [open]);

  const showPause = status === "running";
  const showResume = status !== null && status !== "running";

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
            className="fixed bottom-0 left-0 right-0 z-[61] bg-[#0a0a0a] border-t border-[#1a1a1a] rounded-t-2xl safe-area-bottom"
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-8 h-1 rounded-full bg-[#333]" />
            </div>

            <div className="px-4 pb-6 space-y-4">
              {/* Repo selector */}
              <div>
                <label className="text-[10px] uppercase tracking-[0.15em] text-[#666] font-semibold mb-2 block">
                  Repository
                </label>
                <RepoSelector
                  repos={repos}
                  activeRepo={activeRepo}
                  onSelect={(repo) => { onRepoSelect(repo); onClose(); }}
                />
              </div>

              {/* New Run */}
              <Button
                variant="success"
                size="lg"
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

              {/* Run action button */}
              {showPause && (
                <Button
                  variant="warning"
                  size="lg"
                  disabled={busy}
                  onClick={() => { onPause(); onClose(); }}
                  className="w-full justify-center"
                  icon={
                    <svg width="12" height="12" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="2" y="2" width="2" height="6" rx="0.5" />
                      <rect x="6" y="2" width="2" height="6" rx="0.5" />
                    </svg>
                  }
                >
                  Pause
                </Button>
              )}

              {showResume && (
                <Button
                  variant="success"
                  size="lg"
                  disabled={busy}
                  onClick={() => { onOpenInject(); onClose(); }}
                  className="w-full justify-center"
                  icon={
                    <svg width="12" height="12" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <polygon points="3 2 8 5 3 8" />
                    </svg>
                  }
                >
                  Resume
                </Button>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
