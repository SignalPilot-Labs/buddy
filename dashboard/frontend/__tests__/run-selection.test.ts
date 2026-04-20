/**
 * Run selection regression tests.
 *
 * Verifies that on page load/refresh the dashboard selects the correct
 * run, and that all code paths use handleSelectRun (not bare setSelectedRunId)
 * to keep sidebar highlight and event feed in sync.
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
  const autoSelectStart = DASHBOARD_SRC.indexOf('if (!selectedRunId && runs.length > 0)');
  const autoSelectBlock = DASHBOARD_SRC.slice(
    autoSelectStart,
    DASHBOARD_SRC.indexOf("}, [runs, selectedRunId", autoSelectStart),
  );

  it("checks for active runs before localStorage restore", () => {
    const activeIdx = autoSelectBlock.indexOf('"running"');
    const localStorageIdx = autoSelectBlock.indexOf("localStorage.getItem");
    expect(activeIdx).toBeGreaterThan(-1);
    expect(localStorageIdx).toBeGreaterThan(-1);
    expect(activeIdx).toBeLessThan(localStorageIdx);
  });

  it("returns early when an active run is found", () => {
    // After finding an active run, should call handleSelectRun and return
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
    // localStorage check must come AFTER the active-run early return
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
});

/* ── All selection paths use handleSelectRun ── */

describe("run selection: no bare setSelectedRunId for run switching", () => {
  it("health poll uses handleSelectRun, not setSelectedRunId", () => {
    // Extract the health poll useEffect
    const healthStart = DASHBOARD_SRC.indexOf("fetchAgentHealth");
    const healthBlock = DASHBOARD_SRC.slice(
      healthStart,
      DASHBOARD_SRC.indexOf("clearInterval", healthStart) + 50,
    );
    // Must use handleSelectRun for new run auto-selection
    expect(healthBlock).toContain("handleSelectRun(newRun.run_id)");
    // Must NOT use bare setSelectedRunId (causes sidebar/feed desync)
    expect(healthBlock).not.toContain("setSelectedRunId(newRun.run_id)");
  });

  it("auto-selection effect uses handleSelectRun", () => {
    const autoSelectStart = DASHBOARD_SRC.indexOf('if (!selectedRunId && runs.length > 0)');
    const autoSelectBlock = DASHBOARD_SRC.slice(
      autoSelectStart,
      DASHBOARD_SRC.indexOf("}, [runs, selectedRunId", autoSelectStart),
    );
    // Every run selection in auto-select should go through handleSelectRun
    expect(autoSelectBlock).not.toContain("setSelectedRunId(");
    const handleCalls = autoSelectBlock.match(/handleSelectRun\(/g);
    expect(handleCalls).not.toBeNull();
    expect(handleCalls!.length).toBeGreaterThanOrEqual(3);
  });

  it("handleSelectRun deps include handleSelectRun in health poll effect", () => {
    // The health poll effect must list handleSelectRun in its deps
    const healthEffect = DASHBOARD_SRC.slice(
      DASHBOARD_SRC.indexOf("fetchAgentHealth"),
    );
    const depsMatch = healthEffect.slice(0, healthEffect.indexOf("];") + 2);
    expect(depsMatch).toContain("handleSelectRun");
  });
});
