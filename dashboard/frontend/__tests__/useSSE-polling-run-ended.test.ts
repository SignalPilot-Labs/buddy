/**
 * Regression test: polling fallback must detect run_ended and fire onRunEnded.
 *
 * Before the fix, the polling loop processed audit events but never checked for
 * event_type === "run_ended". The SSE path had a dedicated "run_ended" listener
 * that called onRunEndedRef.current?.() and stopped the connection, but the
 * polling fallback had no equivalent logic. When SSE was unavailable and the run
 * ended, the UI remained stuck in "busy/connected" state forever.
 *
 * The fix scans result.events for a run_ended audit event BEFORE the setEvents
 * updater (to keep side effects outside React state updaters), then after
 * setEvents fires clearInterval, setConnectionState("disconnected"), and
 * onRunEndedRef.current?.().
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useSSE.ts"),
  "utf-8",
);

describe("useSSE polling fallback: run_ended fires onRunEnded and stops polling", () => {
  it("polling loop detects run_ended before calling setEvents", () => {
    const pollingStart = SRC.indexOf("function startPolling()");
    const pollingEnd = SRC.indexOf("function switchToPolling()");
    const pollingBlock = SRC.slice(pollingStart, pollingEnd);

    const hasRunEndedIdx = pollingBlock.indexOf("hasRunEnded");
    const setEventsIdx = pollingBlock.indexOf("setEvents(");

    expect(hasRunEndedIdx).toBeGreaterThan(-1);
    // hasRunEnded detection must appear before the setEvents call
    expect(hasRunEndedIdx).toBeLessThan(setEventsIdx);
  });

  it("polling loop scans for run_ended audit event type", () => {
    const pollingStart = SRC.indexOf("function startPolling()");
    const pollingEnd = SRC.indexOf("function switchToPolling()");
    const pollingBlock = SRC.slice(pollingStart, pollingEnd);

    expect(pollingBlock).toContain('"run_ended"');
    expect(pollingBlock).toContain("hasRunEnded");
  });

  it("polling loop calls clearInterval on pollingRef when run_ended detected", () => {
    const pollingStart = SRC.indexOf("function startPolling()");
    const pollingEnd = SRC.indexOf("function switchToPolling()");
    const pollingBlock = SRC.slice(pollingStart, pollingEnd);

    // The cleanup after setEvents must clear the interval
    const afterSetEvents = pollingBlock.slice(pollingBlock.lastIndexOf("setEvents("));
    expect(afterSetEvents).toContain("clearInterval(pollingRef.current)");
    expect(afterSetEvents).toContain("pollingRef.current = null");
  });

  it("polling loop sets connectionState to disconnected when run_ended detected", () => {
    const pollingStart = SRC.indexOf("function startPolling()");
    const pollingEnd = SRC.indexOf("function switchToPolling()");
    const pollingBlock = SRC.slice(pollingStart, pollingEnd);

    const afterSetEvents = pollingBlock.slice(pollingBlock.lastIndexOf("setEvents("));
    expect(afterSetEvents).toContain('setConnectionState("disconnected")');
  });

  it("polling loop calls onRunEndedRef.current?.() when run_ended detected", () => {
    const pollingStart = SRC.indexOf("function startPolling()");
    const pollingEnd = SRC.indexOf("function switchToPolling()");
    const pollingBlock = SRC.slice(pollingStart, pollingEnd);

    const afterSetEvents = pollingBlock.slice(pollingBlock.lastIndexOf("setEvents("));
    expect(afterSetEvents).toContain("onRunEndedRef.current?.()");
  });

  it("side effects (clearInterval, setConnectionState, onRunEndedRef) are outside setEvents updater", () => {
    const pollingStart = SRC.indexOf("function startPolling()");
    const pollingEnd = SRC.indexOf("function switchToPolling()");
    const pollingBlock = SRC.slice(pollingStart, pollingEnd);

    // Locate the setEvents updater boundaries
    const setEventsIdx = pollingBlock.indexOf("setEvents(");
    // The updater closes with "})" — find the matching one
    // Side effects block must come AFTER the setEvents call closes
    const afterSetEventsClose = pollingBlock.indexOf("});", setEventsIdx);
    const sideEffectsBlock = pollingBlock.slice(afterSetEventsClose);

    expect(sideEffectsBlock).toContain("hasRunEnded");
    expect(sideEffectsBlock).toContain("clearInterval");
    expect(sideEffectsBlock).toContain("onRunEndedRef.current?.()");
  });
});
