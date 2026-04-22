/**
 * Regression test: health poll must NOT contain run selection logic.
 *
 * Run selection belongs in the auto-selection effect only. The health
 * poll should only update agentHealth state and trigger runs refresh.
 * Having selection logic in both places caused races where the health
 * poll re-selected a run that handleStartRun just selected, clearing
 * the pending prompt message.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

describe("health poll: no selection side effects", () => {
  it("health poll does not call handleSelectRun", () => {
    // Extract the health poll effect block
    const startMarker = "// Health poll:";
    const startIdx = SRC.indexOf(startMarker);
    expect(startIdx).toBeGreaterThan(-1);
    // Find the end of this useEffect (next top-level useEffect or function)
    const block = SRC.slice(startIdx, SRC.indexOf("}, [])", startIdx) + 10);
    expect(block).not.toContain("handleSelectRun");
  });

  it("auto-selection only fires when no run is selected", () => {
    // Must never yank user away from a deliberately selected run.
    const autoMarker = "// Auto-selection:";
    const autoIdx = SRC.indexOf(autoMarker);
    expect(autoIdx).toBeGreaterThan(-1);
    const block = SRC.slice(autoIdx, SRC.indexOf("activeRepoFilter])", autoIdx) + 30);
    expect(block).toContain("if (selectedRunId || runs.length === 0) return");
    expect(block).not.toContain("currentIsTerminal");
  });
});
