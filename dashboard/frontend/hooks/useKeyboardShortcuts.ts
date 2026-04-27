"use client";

import { useEffect } from "react";
import { pauseAgent, resumeAgent } from "@/lib/api";
import { ACTIVE_STATUSES } from "@/lib/constants";
import type { RunStatus } from "@/lib/types";

export interface UseKeyboardShortcutsOptions {
  handleToggleSidebar: () => void;
  setStartModalOpen: (v: boolean) => void;
  showShortcuts: boolean;
  setShowShortcuts: (v: boolean) => void;
  controlAction: (label: string, fn: (id: string) => Promise<unknown>) => Promise<void>;
  runStatus: RunStatus | null;
  busy: boolean;
  activeRepoFilter: string | null;
}

export function useKeyboardShortcuts(options: UseKeyboardShortcutsOptions): void {
  const {
    handleToggleSidebar,
    setStartModalOpen,
    showShortcuts,
    setShowShortcuts,
    controlAction,
    runStatus,
    busy,
    activeRepoFilter,
  } = options;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        handleToggleSidebar();
        return;
      }

      const tag = (e.target as HTMLElement)?.tagName;
      const isInput =
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        (e.target as HTMLElement)?.isContentEditable;

      if (isInput) return;

      if (e.key === "n" && !e.metaKey && !e.ctrlKey) {
        if (!activeRepoFilter) return;
        e.preventDefault();
        setStartModalOpen(true);
        return;
      }

      if (e.key === "?") {
        e.preventDefault();
        setShowShortcuts(!showShortcuts);
        return;
      }

      if (e.key === " " && !e.metaKey && !e.ctrlKey) {
        const canControl =
          runStatus !== null &&
          (ACTIVE_STATUSES as readonly RunStatus[]).includes(runStatus) &&
          !busy;
        if (!canControl) return;
        e.preventDefault();
        if (runStatus === "running") {
          void controlAction("Pause", pauseAgent);
        } else if (runStatus === "paused") {
          void controlAction("Resume", resumeAgent);
        }
        return;
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [handleToggleSidebar, setStartModalOpen, showShortcuts, setShowShortcuts, controlAction, runStatus, busy, activeRepoFilter]);
}
