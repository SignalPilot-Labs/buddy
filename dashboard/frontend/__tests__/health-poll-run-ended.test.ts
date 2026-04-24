/**
 * Regression test: health poll must detect when the selected run disappears
 * from the active runs list (indicating run ended) and trigger refreshRuns.
 *
 * Without this fix, a run that ends during an SSE gap (missed run_ended event)
 * leaves runActive stuck as true — the health poll now detects the run
 * disappearing from h.runs and calls refreshRunsRef.current().
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

describe("health poll: run ended detection", () => {
  it("health poll checks for selected run disappearing from h.runs", () => {
    const startMarker = "// Health poll:";
    const startIdx = SRC.indexOf(startMarker);
    expect(startIdx).toBeGreaterThan(-1);
    const block = SRC.slice(startIdx, SRC.indexOf("}, [])", startIdx) + 10);
    // The block must contain logic for detecting a disappeared run
    const hasSelectedGoneCheck =
      block.includes("selectedGone") ||
      block.includes("selectedWasActive") ||
      (block.includes("selectedId") && block.includes("h.runs.some"));
    expect(hasSelectedGoneCheck).toBe(true);
  });

  it("health poll refreshes when selected run disappears", () => {
    const startMarker = "// Health poll:";
    const startIdx = SRC.indexOf(startMarker);
    const block = SRC.slice(startIdx, SRC.indexOf("}, [])", startIdx) + 10);
    // Must call refreshRunsRef.current() when selectedGone is true
    expect(block).toContain("refreshRunsRef.current()");
    // The condition must cover both hasNewRun and the run-disappeared case
    expect(block).toContain("selectedGone");
  });

  it("health poll does not call handleSelectRun (no-reselect invariant preserved)", () => {
    const startMarker = "// Health poll:";
    const startIdx = SRC.indexOf(startMarker);
    const block = SRC.slice(startIdx, SRC.indexOf("}, [])", startIdx) + 10);
    expect(block).not.toContain("handleSelectRun");
  });
});
