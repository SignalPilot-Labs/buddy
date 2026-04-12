"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { FeedEvent, PendingMessage } from "@/lib/types";
import {
  startRun as apiStartRun,
  resumeAgent,
  injectPrompt as apiInjectPrompt,
} from "@/lib/api";
import type { SSECursor } from "@/hooks/useSSE";
import { loadStoredModel } from "@/lib/constants";

export interface UseRunActionsParams {
  selectedRunId: string | null;
  selectedRunIdRef: RefObject<string | null>;
  cursorsRef: RefObject<SSECursor>;
  sseRef: RefObject<{
    connect: (runId: string, cursor: SSECursor) => void;
    disconnect: () => void;
    clearEvents: () => void;
  }>;
  refreshRuns: () => void;
  addEvent: (event: FeedEvent) => void;
  activeRepoFilter: string | null;
  confirmedPrompts: string[];
  handleSelectRun: (id: string) => Promise<FeedEvent[]>;
  setStartModalOpen: (v: boolean) => void;
}

export interface UseRunActionsReturn {
  pendingMessages: PendingMessage[];
  busy: boolean;
  setBusy: (v: boolean) => void;
  addPendingMessage: (prompt: string) => number;
  markPendingFailed: (id: number) => void;
  clearPendingMessages: () => void;
  onRunEnded: () => void;
  handleStartRun: (
    prompt: string | undefined,
    budget: number,
    durationMinutes: number,
    baseBranch: string,
    model?: string,
  ) => Promise<void>;
  handleInject: (prompt: string) => void;
  handleRestart: (prompt: string) => void;
}

export function useRunActions(params: UseRunActionsParams): UseRunActionsReturn {
  const {
    selectedRunId,
    selectedRunIdRef,
    cursorsRef,
    sseRef,
    refreshRuns,
    addEvent,
    activeRepoFilter,
    confirmedPrompts,
    handleSelectRun,
    setStartModalOpen,
  } = params;

  const [busy, setBusy] = useState(false);
  const [pendingMessages, setPendingMessages] = useState<PendingMessage[]>([]);

  const confirmedPromptsRef = useRef<Set<string>>(new Set());

  // Clear confirmed-prompt tracking when confirmedPrompts resets (empty array = run switch)
  useEffect(() => {
    if (confirmedPrompts.length === 0) {
      confirmedPromptsRef.current = new Set();
      return;
    }
    const newConfirmed = confirmedPrompts.filter(
      (t) => !confirmedPromptsRef.current.has(t),
    );
    if (newConfirmed.length === 0) return;
    for (const t of newConfirmed) confirmedPromptsRef.current.add(t);
    const confirmedSet = new Set(newConfirmed);
    setPendingMessages((prev) =>
      prev.filter((m) => m.status !== "pending" || !confirmedSet.has(m.prompt)),
    );
  }, [confirmedPrompts]);

  const clearPendingMessages = useCallback(() => {
    setPendingMessages([]);
  }, []);

  const onRunEnded = useCallback(() => {
    refreshRuns();
    setBusy(false);
    setPendingMessages((prev) => {
      if (prev.length === 0) return prev;
      return prev.map((m) =>
        m.status === "pending" ? { ...m, status: "failed" } : m,
      );
    });
  }, [refreshRuns]);

  const addPendingMessage = useCallback((prompt: string): number => {
    const id = -Date.now();
    setPendingMessages((prev) => [
      ...prev,
      { id, prompt, ts: new Date().toISOString(), status: "pending" },
    ]);
    return id;
  }, []);

  const markPendingFailed = useCallback((id: number) => {
    setPendingMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, status: "failed" } : m)),
    );
  }, []);

  const handleStartRun = useCallback(
    async (
      prompt: string | undefined,
      budget: number,
      durationMinutes: number,
      baseBranch: string,
      model?: string,
    ) => {
      const resolvedModel = model ?? loadStoredModel();
      setStartModalOpen(false);
      setBusy(true);
      try {
        const result = await apiStartRun(
          prompt,
          budget,
          durationMinutes,
          baseBranch,
          resolvedModel,
          activeRepoFilter,
        );
        refreshRuns();
        if (result.run_id) {
          const events = await handleSelectRun(result.run_id);
          if (prompt) {
            const hasPrompt = events.some(
              (e) =>
                e._kind === "audit" &&
                (e.data.event_type === "prompt_submitted" ||
                  e.data.event_type === "prompt_injected"),
            );
            if (!hasPrompt) addPendingMessage(prompt);
          }
        }
      } catch (err) {
        addEvent({
          _kind: "control",
          text: `Failed to start run: ${err}`,
          ts: new Date().toISOString(),
        });
      } finally {
        setBusy(false);
      }
    },
    [addEvent, addPendingMessage, handleSelectRun, refreshRuns, activeRepoFilter, setStartModalOpen],
  );

  const handleInject = useCallback(
    (prompt: string) => {
      if (!selectedRunId) return;
      const pid = addPendingMessage(prompt);
      apiInjectPrompt(selectedRunId, prompt).catch((e) => {
        markPendingFailed(pid);
        addEvent({
          _kind: "control",
          text: `Inject failed: ${e}`,
          ts: new Date().toISOString(),
        });
      });
    },
    [selectedRunId, addPendingMessage, markPendingFailed, addEvent],
  );

  const handleRestart = useCallback(
    (prompt: string) => {
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
          addEvent({
            _kind: "control",
            text: `Restart failed: ${e}`,
            ts: new Date().toISOString(),
          });
        });
    },
    [
      selectedRunId,
      selectedRunIdRef,
      cursorsRef,
      sseRef,
      addPendingMessage,
      markPendingFailed,
      addEvent,
    ],
  );

  return {
    pendingMessages,
    busy,
    setBusy,
    addPendingMessage,
    markPendingFailed,
    clearPendingMessages,
    onRunEnded,
    handleStartRun,
    handleInject,
    handleRestart,
  };
}
