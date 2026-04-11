import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { FeedEvent, PendingMessage } from "@/lib/types";
import { pollEvents } from "@/lib/api";
import { mergeToolEvent } from "@/lib/eventMerge";
import { loadRunHistory } from "@/lib/loadRunHistory";

export interface SSERef {
  connect: (runId: string, cursor: { afterTool: number; afterAudit: number }, onConnected?: () => void) => void;
  disconnect: () => void;
  clearEvents: () => void;
}

export interface Cursors {
  afterTool: number;
  afterAudit: number;
}

export function applyCatchUpEvents(
  runId: string,
  afterTool: number,
  afterAudit: number,
  setHistoryEvents: Dispatch<SetStateAction<FeedEvent[]>>,
  cursorsRef: MutableRefObject<Cursors>,
): void {
  pollEvents(runId, afterTool, afterAudit).then((result) => {
    if (result.tool_calls.length === 0 && result.audit_events.length === 0) return;
    let newAfterTool = afterTool;
    let newAfterAudit = afterAudit;
    setHistoryEvents((prev) => {
      let next = prev;
      for (const tc of result.tool_calls) {
        newAfterTool = Math.max(newAfterTool, tc.id);
        next = mergeToolEvent(next, tc);
      }
      for (const ae of result.audit_events) {
        newAfterAudit = Math.max(newAfterAudit, ae.id);
        const details =
          typeof ae.details === "string"
            ? (JSON.parse(ae.details) as Record<string, unknown>)
            : ae.details;
        next = [...next, { _kind: "audit", data: { ...ae, details } }];
      }
      return next;
    });
    cursorsRef.current = { afterTool: newAfterTool, afterAudit: newAfterAudit };
  }).catch((err) => {
    setHistoryEvents((prev) => [
      ...prev,
      { _kind: "control", text: `Catch-up poll failed: ${err}`, ts: new Date().toISOString() },
    ]);
  });
}

export function reconnectAfterResume(
  runId: string,
  sseRef: MutableRefObject<SSERef>,
  cursorsRef: MutableRefObject<Cursors>,
  setHistoryEvents: Dispatch<SetStateAction<FeedEvent[]>>,
  setHistoryLoading: Dispatch<SetStateAction<boolean>>,
  setPendingMessages: Dispatch<SetStateAction<PendingMessage[]>>,
): void {
  sseRef.current.disconnect();
  setPendingMessages([]);
  setHistoryLoading(true);
  loadRunHistory(runId).then(({ events, lastToolId, lastAuditId }) => {
    setHistoryEvents(events);
    cursorsRef.current = { afterTool: lastToolId, afterAudit: lastAuditId };
    sseRef.current.clearEvents();
    sseRef.current.connect(runId, { afterTool: lastToolId, afterAudit: lastAuditId }, () => {
      applyCatchUpEvents(runId, lastToolId, lastAuditId, setHistoryEvents, cursorsRef);
    });
    setHistoryLoading(false);
  }).catch((err) => {
    setHistoryLoading(false);
    setHistoryEvents((prev) => [
      ...prev,
      { _kind: "control", text: `Session resume failed: ${err}`, ts: new Date().toISOString() },
    ]);
  });
}
