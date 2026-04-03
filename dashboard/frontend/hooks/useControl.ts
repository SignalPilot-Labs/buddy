"use client";

import { useState, useCallback, useRef } from "react";
import {
  sendSignal,
  injectPrompt,
  unlockSession,
  stopAgentInstant,
  killAgent,
  resumeRun,
} from "@/lib/api";
import { DEFAULT_BUDGET_USD } from "@/lib/constants";
import type { FeedEvent } from "@/lib/types";

export function useControl(
  runId: string | null,
  addEvent: (event: FeedEvent) => void
) {
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  const exec = useCallback(
    async (action: () => Promise<unknown>, label: string) => {
      if (busyRef.current) return;
      setBusy(true);
      busyRef.current = true;
      try {
        await action();
        addEvent({
          _kind: "control",
          text: label,
          ts: new Date().toISOString(),
        });
      } catch (err) {
        addEvent({
          _kind: "control",
          text: `Failed: ${label} — ${err}`,
          ts: new Date().toISOString(),
        });
      } finally {
        setBusy(false);
        busyRef.current = false;
      }
    },
    [addEvent]
  );

  const pause = useCallback(
    () => {
      if (!runId) return;
      return exec(() => sendSignal(runId, "pause"), "Pause signal sent");
    },
    [exec, runId]
  );

  const resume = useCallback(
    () => {
      if (!runId) return;
      return exec(() => sendSignal(runId, "resume"), "Resume signal sent");
    },
    [exec, runId]
  );

  // Instant stop — pushes directly to the agent's in-process queue
  const stop = useCallback(
    () => exec(() => stopAgentInstant(), "STOP sent (instant)"),
    [exec]
  );

  // Kill — immediately cancels the asyncio task, no cleanup
  const kill = useCallback(
    () => exec(() => killAgent(), "KILL sent — task cancelled immediately"),
    [exec]
  );

  const inject = useCallback(
    (prompt: string) => {
      if (!runId) return;
      return exec(
        () => injectPrompt(runId, prompt),
        `Prompt injected (${prompt.length} chars)`
      );
    },
    [exec, runId]
  );

  const unlock = useCallback(
    () => {
      if (!runId) return;
      return exec(
        () => unlockSession(runId),
        "Session gate unlocked — agent can now call end_session"
      );
    },
    [exec, runId]
  );

  const resumeSession = useCallback(
    () => {
      if (!runId) return;
      return exec(
        () => resumeRun(runId, DEFAULT_BUDGET_USD),
        "Resuming previous session..."
      );
    },
    [exec, runId]
  );

  return { pause, resume, stop, kill, inject, unlock, resumeSession, busy };
}
