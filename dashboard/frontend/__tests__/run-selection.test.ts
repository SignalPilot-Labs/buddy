/**
 * Run selection regression tests.
 *
 * Verifies that on page load/refresh the dashboard selects the correct
 * run, and that all code paths use handleSelectRun (not bare setSelectedRunId)
 * to keep sidebar highlight and event feed in sync.
 *
 * Run selection lives ONLY in the auto-selection effect. The health poll
 * must NOT contain selection logic (causes races with handleStartRun).
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const DASHBOARD_SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

/* ── Auto-selection priority on page load ── */

describe("run auto-selection: active runs take priority", () => {
  // Extract the auto-selection useEffect block
  const autoSelectStart = DASHBOARD_SRC.indexOf("// Auto-selection:");
  const autoSelectBlock = DASHBOARD_SRC.slice(
    autoSelectStart,
    DASHBOARD_SRC.indexOf("activeRepoFilter])", autoSelectStart) + 30,
  );

  it("checks for active runs before localStorage restore", () => {
    const activeIdx = autoSelectBlock.indexOf('"running"');
    const localStorageIdx = autoSelectBlock.indexOf("localStorage.getItem");
    expect(activeIdx).toBeGreaterThan(-1);
    expect(localStorageIdx).toBeGreaterThan(-1);
    expect(activeIdx).toBeLessThan(localStorageIdx);
  });

  it("returns early when an active run is found and none selected", () => {
    const activeBlock = autoSelectBlock.slice(
      autoSelectBlock.indexOf('"running"'),
    );
    const handleCall = activeBlock.indexOf("handleSelectRun(active.id)");
    const returnAfter = activeBlock.indexOf("return;", handleCall);
    expect(handleCall).toBeGreaterThan(-1);
    expect(returnAfter).toBeGreaterThan(-1);
    expect(returnAfter - handleCall).toBeLessThan(50);
  });

  it("falls back to localStorage only when no active run exists", () => {
    const lines = autoSelectBlock.split("\n");
    let foundActiveReturn = false;
    let foundLocalStorage = false;
    for (const line of lines) {
      if (line.includes("handleSelectRun(active.id)")) foundActiveReturn = true;
      if (line.includes("localStorage.getItem")) {
        foundLocalStorage = true;
        expect(foundActiveReturn).toBe(true);
      }
    }
    expect(foundLocalStorage).toBe(true);
  });

  it("falls back to runs[0] as last resort", () => {
    expect(autoSelectBlock).toContain("handleSelectRun(runs[0].id)");
  });

  it("switches from terminal run to active run", () => {
    expect(autoSelectBlock).toContain("currentIsTerminal");
    expect(autoSelectBlock).toContain("active.id !== selectedRunId");
  });
});

/* ── Health poll has no selection side effects ── */

describe("run selection: health poll only refreshes, no selection", () => {
  it("health poll does NOT call handleSelectRun", () => {
    const healthStart = DASHBOARD_SRC.indexOf("// Health poll:");
    const healthBlock = DASHBOARD_SRC.slice(
      healthStart,
      DASHBOARD_SRC.indexOf("}, [])", healthStart) + 10,
    );
    expect(healthBlock).not.toContain("handleSelectRun");
  });

  it("health poll does NOT call setSelectedRunId", () => {
    const healthStart = DASHBOARD_SRC.indexOf("// Health poll:");
    const healthBlock = DASHBOARD_SRC.slice(
      healthStart,
      DASHBOARD_SRC.indexOf("}, [])", healthStart) + 10,
    );
    expect(healthBlock).not.toContain("setSelectedRunId");
  });

  it("health poll triggers refreshRunsRef on new run", () => {
    const healthStart = DASHBOARD_SRC.indexOf("// Health poll:");
    const healthBlock = DASHBOARD_SRC.slice(
      healthStart,
      DASHBOARD_SRC.indexOf("}, [])", healthStart) + 10,
    );
    expect(healthBlock).toContain("refreshRunsRef.current()");
  });
});

/* ── All selection paths use handleSelectRun ── */

describe("run selection: no bare setSelectedRunId for run switching", () => {
  it("auto-selection effect uses handleSelectRun", () => {
    const autoSelectStart = DASHBOARD_SRC.indexOf("// Auto-selection:");
    const autoSelectBlock = DASHBOARD_SRC.slice(
      autoSelectStart,
      DASHBOARD_SRC.indexOf("activeRepoFilter])", autoSelectStart) + 30,
    );
    expect(autoSelectBlock).not.toContain("setSelectedRunId(");
    const handleCalls = autoSelectBlock.match(/handleSelectRun\(/g);
    expect(handleCalls).not.toBeNull();
    expect(handleCalls!.length).toBeGreaterThanOrEqual(3);
  });
});
