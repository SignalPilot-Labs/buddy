"use client";

import { useState, useCallback } from "react";
import {
  startRun as apiStartRun,
  stopRun,
  resumeAgent,
  injectPrompt as apiInjectPrompt,
} from "@/lib/api";
import { loadStoredModel } from "@/lib/constants";
import type { RunActionsConfig, RunActions } from "@/hooks/dashboardTypes";

export function useRunActions(config: RunActionsConfig): RunActions {
  const {
    selectedRunId,
    addEvent,
    refreshRunsRef,
    handleSelectRun,
    activeRepoFilter,
    setStartModalOpen,
    setBusy,
  } = config;

  const [showStopDialog, setShowStopDialog] = useState(false);

  const controlAction = useCallback(
    (label: string, fn: (id: string) => Promise<unknown>): Promise<void> => {
      if (!selectedRunId) return Promise.resolve();
      return fn(selectedRunId)
        .then(() => undefined)
        .catch((e: unknown) => {
          const retry = () => controlAction(label, fn);
          addEvent({
            _kind: "control",
            text: `${label} failed: ${e}`,
            ts: new Date().toISOString(),
            retryAction: retry,
          });
          return Promise.reject(e);
        });
    },
    [selectedRunId, addEvent],
  );

  const handleStartRun = useCallback(
    async (
      prompt: string | undefined,
      preset: string | undefined,
      budget: number,
      durationMinutes: number,
      baseBranch: string,
      model?: string | undefined,
      effort?: string | undefined,
    ): Promise<void> => {
      const resolvedModel = model ?? loadStoredModel();
      const resolvedEffort = effort ?? "high";
      setStartModalOpen(false);
      setBusy(true);
      try {
        const result = await apiStartRun(prompt, preset, budget, durationMinutes, baseBranch, resolvedModel, resolvedEffort, activeRepoFilter);
        await refreshRunsRef.current();
        if (result.run_id) {
          await handleSelectRun(result.run_id);
        }
      } catch (err) {
        addEvent({ _kind: "control", text: `Failed to start run: ${err}`, ts: new Date().toISOString() });
      } finally {
        setBusy(false);
      }
    },
    [addEvent, handleSelectRun, activeRepoFilter, setStartModalOpen, setBusy, refreshRunsRef],
  );

  const handleInject = useCallback(
    (prompt: string): void => {
      if (!selectedRunId) return;
      apiInjectPrompt(selectedRunId, prompt).catch((e) => {
        addEvent({ _kind: "control", text: `Inject failed: ${e}`, ts: new Date().toISOString() });
      });
    },
    [selectedRunId, addEvent],
  );

  const handleRestart = useCallback(
    (prompt?: string): void => {
      if (!selectedRunId) return;
      resumeAgent(selectedRunId, prompt)
        .then(async () => {
          await refreshRunsRef.current();
          void handleSelectRun(selectedRunId);
        })
        .catch((e) => {
          addEvent({ _kind: "control", text: `Resume failed: ${e}`, ts: new Date().toISOString() });
        });
    },
    [selectedRunId, addEvent, refreshRunsRef, handleSelectRun],
  );

  const handleStopClick = useCallback((): void => {
    setShowStopDialog(true);
  }, []);

  const handleStopConfirm = useCallback(
    (openPr: boolean): void => {
      setShowStopDialog(false);
      setBusy(true);
      controlAction("Stop", (id) => stopRun(id, !openPr)).catch(() => {
        setBusy(false);
      });
    },
    [controlAction, setBusy],
  );

  const handleStopCancel = useCallback((): void => {
    setShowStopDialog(false);
  }, []);

  return {
    controlAction,
    handleStartRun,
    handleInject,
    handleRestart,
    showStopDialog,
    handleStopClick,
    handleStopConfirm,
    handleStopCancel,
  };
}
