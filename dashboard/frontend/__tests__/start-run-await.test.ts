/**
 * Regression test: handleStartRun must await refreshRunsRef before selecting.
 *
 * Without await, handleSelectRun races with the runs list fetch — the new
 * run isn't in the sidebar yet when SSE connects, causing a stale feed
 * and wrong selection. Same applies to handleRestart.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useRunActions.ts"),
  "utf-8",
);

describe("start run: refresh must be awaited before selection", () => {
  it("handleStartRun awaits refreshRunsRef before handleSelectRun", () => {
    // Extract the handleStartRun block
    const startIdx = SRC.indexOf("handleStartRun");
    const block = SRC.slice(startIdx, SRC.indexOf("handleInject"));
    // refreshRunsRef.current() must be awaited
    expect(block).toContain("await refreshRunsRef.current()");
    // handleSelectRun must come AFTER the await
    const awaitPos = block.indexOf("await refreshRunsRef.current()");
    const selectPos = block.indexOf("handleSelectRun(result.run_id)");
    expect(selectPos).toBeGreaterThan(awaitPos);
  });

  it("handleRestart awaits refreshRunsRef before handleSelectRun", () => {
    const restartIdx = SRC.indexOf("handleRestart");
    const block = SRC.slice(restartIdx, SRC.indexOf("handleStopClick"));
    expect(block).toContain("await refreshRunsRef.current()");
    const awaitPos = block.indexOf("await refreshRunsRef.current()");
    const selectPos = block.indexOf("handleSelectRun(selectedRunId)");
    expect(selectPos).toBeGreaterThan(awaitPos);
  });
});
