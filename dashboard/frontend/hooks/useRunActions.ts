"use client";

import { useState, useCallback } from "react";
import {
  startRun as apiStartRun,
  killAgent,
  resumeAgent,
  injectPrompt as apiInjectPrompt,
} from "@/lib/api";
import { loadStoredModel } from "@/lib/constants";
import type { RunActionsConfig, RunActions } from "@/hooks/dashboardTypes";

const KILL_CONFIRM_TIMEOUT_MS = 3000;

export function useRunActions(config: RunActionsConfig): RunActions {
  const {
    selectedRunId,
    selectedRunIdRef,
    addEvent,
    addPendingMessage,
    markPendingFailed,
    sseRef,
    cursorsRef,
    refreshRunsRef,
    handleSelectRun,
    activeRepoFilter,
    setStartModalOpen,
    setBusy,
  } = config;

  const [showKillConfirm, setShowKillConfirm] = useState(false);

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
      budget: number,
      durationMinutes: number,
      baseBranch: string,
      model?: string | undefined,
    ): Promise<void> => {
      const resolvedModel = model ?? loadStoredModel();
      setStartModalOpen(false);
      setBusy(true);
      try {
        const result = await apiStartRun(prompt, budget, durationMinutes, baseBranch, resolvedModel, activeRepoFilter);
        refreshRunsRef.current();
        if (result.run_id) {
          const events = await handleSelectRun(result.run_id);
          if (prompt) {
            const hasPrompt = events.some(
              (e) =>
                e._kind === "audit" &&
                (e.data.event_type === "prompt_submitted" || e.data.event_type === "prompt_injected"),
            );
            if (!hasPrompt) addPendingMessage(prompt);
          }
        }
      } catch (err) {
        addEvent({ _kind: "control", text: `Failed to start run: ${err}`, ts: new Date().toISOString() });
      } finally {
        setBusy(false);
      }
    },
    [addEvent, addPendingMessage, handleSelectRun, activeRepoFilter, setStartModalOpen, setBusy, refreshRunsRef],
  );

  const handleInject = useCallback(
    (prompt: string): void => {
      if (!selectedRunId) return;
      const pid = addPendingMessage(prompt);
      apiInjectPrompt(selectedRunId, prompt).catch((e) => {
        markPendingFailed(pid);
        addEvent({ _kind: "control", text: `Inject failed: ${e}`, ts: new Date().toISOString() });
      });
    },
    [selectedRunId, addPendingMessage, markPendingFailed, addEvent],
  );

  const handleRestart = useCallback(
    (prompt: string): void => {
      if (!selectedRunId) return;
      const pid = prompt ? addPendingMessage(prompt) : 0;
      resumeAgent(selectedRunId, prompt)
        .then(() => {
          const runId = selectedRunIdRef.current;
          if (runId) {
            sseRef.current.disconnect();
            sseRef.current.clearEvents();
            sseRef.current.connect(runId, cursorsRef.current);
          }
        })
        .catch((e) => {
          if (pid) markPendingFailed(pid);
          addEvent({ _kind: "control", text: `Restart failed: ${e}`, ts: new Date().toISOString() });
        });
    },
    [selectedRunId, selectedRunIdRef, addPendingMessage, markPendingFailed, addEvent, sseRef, cursorsRef],
  );

  const handleHeaderKill = useCallback((): void => {
    if (!showKillConfirm) {
      setShowKillConfirm(true);
      setTimeout(() => setShowKillConfirm(false), KILL_CONFIRM_TIMEOUT_MS);
      return;
    }
    setBusy(true);
    void controlAction("Kill", killAgent);
    setShowKillConfirm(false);
  }, [showKillConfirm, controlAction, setBusy]);

  return {
    controlAction,
    handleStartRun,
    handleInject,
    handleRestart,
    handleHeaderKill,
    showKillConfirm,
  };
}
