/**
 * Regression tests: pending messages must be cleared when the matching
 * prompt_injected audit event arrives — whether via liveEvents or historyEvents.
 *
 * Bug: injected messages appeared twice in the feed — once as the pending
 * card and once as the confirmed audit event. The dedup only checked
 * liveEvents, missing events that landed in historyEvents.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useEventState.ts"),
  "utf-8",
);

describe("pending message dedup: checks both history and live events", () => {
  it("dedup effect depends on both liveEvents and historyEvents", () => {
    // The useEffect that clears pending messages must react to BOTH sources.
    // Previously it only depended on [liveEvents], missing history-delivered events.
    const effectBlock = SRC.slice(
      SRC.indexOf("// Clear pending messages"),
      SRC.indexOf("}, ["),
    );
    // Find the dependency array for this effect
    const depsStart = SRC.indexOf("}, [", SRC.indexOf("// Clear pending messages"));
    const depsEnd = SRC.indexOf("])", depsStart);
    const deps = SRC.slice(depsStart, depsEnd + 2);

    expect(deps).toContain("liveEvents");
    expect(deps).toContain("historyEvents");
  });

  it("dedup scans historyEvents for prompt_injected", () => {
    // The confirmedTexts extraction must include historyEvents, not just liveEvents
    const effectBlock = SRC.slice(
      SRC.indexOf("// Clear pending messages"),
      SRC.indexOf("}, [liveEvents, historyEvents]"),
    );
    expect(effectBlock).toContain("historyEvents");
    expect(effectBlock).toContain("prompt_injected");
  });

  it("dedup resets when both sources are empty", () => {
    // On run switch, both history and live are cleared. The confirmed set must reset.
    const effectBlock = SRC.slice(
      SRC.indexOf("// Clear pending messages"),
      SRC.indexOf("}, [liveEvents, historyEvents]"),
    );
    // Must check combined length, not just liveEvents.length
    expect(effectBlock).toContain("allEvents.length === 0");
    expect(effectBlock).not.toMatch(/if \(liveEvents\.length === 0\)/);
  });
});
