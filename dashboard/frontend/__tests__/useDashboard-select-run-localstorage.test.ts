/**
 * Regression tests for handleSelectRun persisting invalid run IDs to
 * localStorage before verifying the load succeeded (BUG 10).
 *
 * Root cause: localStorage.setItem("autofyn_last_run_id", id) was called
 * immediately after setSelectedRunId(id) — before loadRunHistory even
 * started. If loadRunHistory failed (network error, 404, etc.), the invalid
 * run ID was already persisted. On next load, the auto-selection effect would
 * try to restore this ID via handleSelectRun, which would fail again.
 *
 * Fix: Move localStorage.setItem inside the try block, after
 * setHistoryTruncatedRef.current(result.truncated) and before assigning
 * loadedEvents. Only runs that load successfully are persisted.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

describe("useDashboard: handleSelectRun localStorage timing (BUG 10)", () => {
  it("localStorage.setItem for autofyn_last_run_id appears inside the try block", () => {
    const fnStart = SRC.indexOf("const handleSelectRun");
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = SRC.indexOf("\n  );", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 10);

    const tryStart = fnBody.indexOf("try {");
    const catchStart = fnBody.indexOf("} catch (err)");
    const localStorageSetPos = fnBody.indexOf('localStorage.setItem("autofyn_last_run_id"');

    expect(tryStart).toBeGreaterThan(-1);
    expect(catchStart).toBeGreaterThan(-1);
    expect(localStorageSetPos).toBeGreaterThan(-1);

    // The setItem must be between try { and } catch
    expect(localStorageSetPos).toBeGreaterThan(tryStart);
    expect(localStorageSetPos).toBeLessThan(catchStart);
  });

  it("localStorage.setItem appears AFTER loadRunHistory completes (after setHistoryTruncatedRef)", () => {
    const fnStart = SRC.indexOf("const handleSelectRun");
    const fnEnd = SRC.indexOf("\n  );", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 10);

    const loadHistoryPos = fnBody.indexOf("await loadRunHistory(id)");
    const truncatedPos = fnBody.indexOf("setHistoryTruncatedRef.current(result.truncated)");
    const localStorageSetPos = fnBody.indexOf('localStorage.setItem("autofyn_last_run_id"');

    expect(loadHistoryPos).toBeGreaterThan(-1);
    expect(truncatedPos).toBeGreaterThan(-1);
    expect(localStorageSetPos).toBeGreaterThan(-1);

    // localStorage.setItem must come after loadRunHistory completes
    expect(localStorageSetPos).toBeGreaterThan(loadHistoryPos);
    // And after the truncated ref is set
    expect(localStorageSetPos).toBeGreaterThan(truncatedPos);
  });

  it("localStorage.setItem appears BEFORE loadedEvents assignment", () => {
    const fnStart = SRC.indexOf("const handleSelectRun");
    const fnEnd = SRC.indexOf("\n  );", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 10);

    const localStorageSetPos = fnBody.indexOf('localStorage.setItem("autofyn_last_run_id"');
    const loadedEventsAssignPos = fnBody.indexOf("loadedEvents = result.events");

    expect(localStorageSetPos).toBeGreaterThan(-1);
    expect(loadedEventsAssignPos).toBeGreaterThan(-1);
    expect(localStorageSetPos).toBeLessThan(loadedEventsAssignPos);
  });

  it("localStorage.setItem is NOT called before the try block", () => {
    const fnStart = SRC.indexOf("const handleSelectRun");
    const fnEnd = SRC.indexOf("\n  );", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 10);

    const tryStart = fnBody.indexOf("try {");
    // No localStorage.setItem for last_run_id should appear before try {
    const prelude = fnBody.slice(0, tryStart);
    expect(prelude).not.toContain('localStorage.setItem("autofyn_last_run_id"');
  });

  it("handleSelectRun still uses generation counter to guard stale results", () => {
    const fnStart = SRC.indexOf("const handleSelectRun");
    const fnEnd = SRC.indexOf("\n  );", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 10);

    expect(fnBody).toContain("const gen = ++selectGenRef.current");
    expect(fnBody).toContain("gen !== selectGenRef.current");
  });
});
