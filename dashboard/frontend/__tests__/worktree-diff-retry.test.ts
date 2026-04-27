/**
 * Regression test: WorkTree must not get stuck when the initial fetchRunDiff fails.
 *
 * Before the fix, if fetchRunDiff(runId) failed in the initial mount effect,
 * diffData remained null. The polling condition (isPollingSource) requires
 * diffData?.source === "live" | "agent", which is false for null — so the
 * polling interval never started and the component showed an empty state forever.
 *
 * The fix sets diffData to a live-source sentinel in the catch block so that
 * isPollingSource becomes true and the existing polling interval retries the
 * fetch automatically.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/worktree/WorkTree.tsx"),
  "utf-8",
);

describe("WorkTree: diff fetch retry via live sentinel on initial failure", () => {
  it("catch block in initial fetch effect calls setDiffData", () => {
    // Locate the initial fetch effect (not the polling interval)
    const effectStart = SRC.indexOf("fetchRunDiff(runId)");
    const catchStart = SRC.indexOf(".catch(", effectStart);
    const catchEnd = SRC.indexOf("});", catchStart);
    const catchBlock = SRC.slice(catchStart, catchEnd + 3);
    expect(catchBlock).toContain("setDiffData(");
  });

  it("catch block sets source to 'live' to enable polling retry", () => {
    const effectStart = SRC.indexOf("fetchRunDiff(runId)");
    const catchStart = SRC.indexOf(".catch(", effectStart);
    const catchEnd = SRC.indexOf("});", catchStart);
    const catchBlock = SRC.slice(catchStart, catchEnd + 3);
    expect(catchBlock).toContain('"live"');
  });

  it("catch block sets empty files array in sentinel", () => {
    const effectStart = SRC.indexOf("fetchRunDiff(runId)");
    const catchStart = SRC.indexOf(".catch(", effectStart);
    const catchEnd = SRC.indexOf("});", catchStart);
    const catchBlock = SRC.slice(catchStart, catchEnd + 3);
    expect(catchBlock).toContain("files: []");
  });

  it("isPollingSource checks for 'live' source which sentinel satisfies", () => {
    expect(SRC).toContain('diffData?.source === "live"');
  });
});
