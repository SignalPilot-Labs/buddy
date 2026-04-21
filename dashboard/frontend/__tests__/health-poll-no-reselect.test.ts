/**
 * Regression test: health poll must not re-select the already-selected run.
 *
 * When handleStartRun selects a new run and adds a pending message,
 * the health poll should not call handleSelectRun again for the same
 * run — doing so clears pending messages and the prompt disappears.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

describe("health poll: no re-selection of current run", () => {
  it("health poll checks newRun.run_id !== currentId before selecting", () => {
    // Find the health poll effect that detects new runs
    const healthBlock = SRC.slice(
      SRC.indexOf("const check = async"),
      SRC.indexOf("check();\n"),
    );
    // Must guard against re-selecting the same run
    expect(healthBlock).toContain("newRun.run_id !== currentId");
  });
});
