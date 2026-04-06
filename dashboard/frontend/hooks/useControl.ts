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
import type { FeedEvent } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";

export function useControl(
  runId: string | null,
  addEvent: (event: FeedEvent) => void
) {
  const { t } = useTranslation();
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
          text: `${t.useControl.failed}: ${label} — ${err}`,
          ts: new Date().toISOString(),
        });
      } finally {
        setBusy(false);
        busyRef.current = false;
      }
    },
    [addEvent, t]
  );

  const pause = useCallback(
    () => {
      if (!runId) return;
      return exec(() => sendSignal(runId, "pause"), t.useControl.pauseSent);
    },
    [exec, runId, t]
  );

  const resume = useCallback(
    () => {
      if (!runId) return;
      return exec(() => sendSignal(runId, "resume"), t.useControl.resumeSent);
    },
    [exec, runId, t]
  );

  // Instant stop — pushes directly to the agent's in-process queue
  const stop = useCallback(
    () => exec(() => stopAgentInstant(), t.useControl.stopSent),
    [exec, t]
  );

  // Kill — immediately cancels the asyncio task, no cleanup
  const kill = useCallback(
    () => exec(() => killAgent(), t.useControl.killSent),
    [exec, t]
  );

  const inject = useCallback(
    (prompt: string) => {
      if (!runId) return;
      return exec(
        () => injectPrompt(runId, prompt),
        `${t.useControl.promptInjected} (${prompt.length} ${t.useControl.chars})`
      );
    },
    [exec, runId, t]
  );

  const unlock = useCallback(
    () => {
      if (!runId) return;
      return exec(
        () => unlockSession(runId),
        t.useControl.sessionUnlocked
      );
    },
    [exec, runId, t]
  );

  const resumeSession = useCallback(
    () => {
      if (!runId) return;
      return exec(
        () => resumeRun(runId),
        t.useControl.resumingSession
      );
    },
    [exec, runId, t]
  );

  return { pause, resume, stop, kill, inject, unlock, resumeSession, busy };
}
