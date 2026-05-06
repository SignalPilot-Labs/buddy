/**
 * Regression tests for useDashboard handleRepoSwitch not cancelling in-flight
 * loadRunHistory calls (BUG 11).
 *
 * Root cause: handleSelectRun increments selectGenRef.current to invalidate
 * stale loadRunHistory results. But handleRepoSwitch did not increment
 * selectGenRef.current, so an in-flight loadRunHistory from before the repo
 * switch could resolve and write stale events if no new run had been selected
 * (leaving selectGenRef unchanged).
 *
 * Fix: Add selectGenRef.current += 1 immediately after sseRef.current.disconnect()
 * in handleRepoSwitch, before setSelectedRunId(null). This invalidates any
 * in-flight loadRunHistory call from the old repo.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

describe("useDashboard: handleRepoSwitch cancels in-flight loadRunHistory (BUG 11)", () => {
  it("handleRepoSwitch contains selectGenRef.current += 1", () => {
    const fnStart = SRC.indexOf("const handleRepoSwitch");
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = SRC.indexOf("\n  }, [])", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 20);

    expect(fnBody).toContain("selectGenRef.current += 1");
  });

  it("selectGenRef increment appears after sseRef.current.disconnect() and before setSelectedRunId(null)", () => {
    const fnStart = SRC.indexOf("const handleRepoSwitch");
    const fnEnd = SRC.indexOf("\n  }, [])", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 20);

    const disconnectPos = fnBody.indexOf("sseRef.current.disconnect()");
    const incrementPos = fnBody.indexOf("selectGenRef.current += 1");
    const setRunIdPos = fnBody.indexOf("setSelectedRunId(null)");

    expect(disconnectPos).toBeGreaterThan(0);
    expect(incrementPos).toBeGreaterThan(disconnectPos);
    expect(setRunIdPos).toBeGreaterThan(incrementPos);
  });

  it("handleSelectRun also uses selectGenRef to guard stale results", () => {
    const fnStart = SRC.indexOf("const handleSelectRun");
    const fnEnd = SRC.indexOf("\n  );", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 10);

    expect(fnBody).toContain("selectGenRef.current");
    expect(fnBody).toContain("gen !== selectGenRef.current");
  });

  it("selectGenRef is declared as useRef(0) at the top of the hook", () => {
    expect(SRC).toContain("const selectGenRef = useRef(0)");
  });
});
