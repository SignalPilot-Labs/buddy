/**
 * Regression test: handleStopConfirm must clear busy on API failure.
 *
 * Before the fix, `void controlAction(...)` discarded the rejection, so
 * `setBusy(false)` was never called when `stopRun` failed — permanently
 * locking the UI. The fix chains `.catch(() => { setBusy(false); })`.
 *
 * We also verify `.finally` is NOT used, because `.finally` would clear
 * busy on success too — before the SSE `run_ended` event fires — causing
 * a flash of unlocked state that then re-locks.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useRunActions.ts"),
  "utf-8",
);

describe("handleStopConfirm: busy lock must clear on API failure", () => {
  it("handleStopConfirm chains .catch that clears busy", () => {
    const stopIdx = SRC.indexOf("handleStopConfirm");
    const block = SRC.slice(stopIdx, SRC.indexOf("handleStopCancel"));
    // Must call controlAction without void-discarding the promise
    expect(block).not.toContain("void controlAction");
    // Must attach a .catch handler
    expect(block).toContain(".catch(");
    // The catch handler must call setBusy(false).
    // Use the closing `});` of the catch to find the full body (inner braces
    // from if-blocks mean the first `}` is not necessarily the catch end).
    const catchStart = block.indexOf(".catch(");
    const catchEnd = block.indexOf("});", catchStart);
    const catchBlock = block.slice(catchStart, catchEnd + 3);
    expect(catchBlock).toContain("setBusy(false)");
  });

  it("handleStopConfirm does not use .finally", () => {
    const stopIdx = SRC.indexOf("handleStopConfirm");
    const block = SRC.slice(stopIdx, SRC.indexOf("handleStopCancel"));
    // .finally would clear busy on success before SSE run_ended fires
    expect(block).not.toContain(".finally");
  });
});
