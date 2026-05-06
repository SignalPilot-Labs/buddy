/**
 * Regression tests for EventFeed seenCount drift (BUG 13).
 *
 * Root cause: When events.length decreased (run switch, clear, filter) while
 * the user was scrolled away (userScrolled=true), seenCount was not reset.
 * The subsequent newEventCount calculation: Math.max(0, events.length - seenCount)
 * produced 0 even when new events had arrived, so the FAB showed "Jump to latest"
 * instead of "N new events".
 *
 * Fix: Added an else-if branch in the seenCount useEffect that resets seenCount
 * to events.length when events.length < seenCount, regardless of userScrolled.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/feed/EventFeed.tsx"),
  "utf-8",
);

describe("EventFeed: seenCount reset on events.length drop (BUG 13)", () => {
  it("seenCount effect contains else-if branch for events.length < seenCount", () => {
    // Find the seenCount useEffect block
    const effectStart = SRC.indexOf("Track how many events were seen");
    expect(effectStart).toBeGreaterThan(-1);

    const effectEnd = SRC.indexOf("}, [userScrolled, events.length, seenCount]);", effectStart);
    expect(effectEnd).toBeGreaterThan(effectStart);

    const effectBody = SRC.slice(effectStart, effectEnd + 45);
    expect(effectBody).toContain("events.length < seenCount");
  });

  it("seenCount effect resets seenCount to events.length when length drops", () => {
    const effectStart = SRC.indexOf("Track how many events were seen");
    const effectEnd = SRC.indexOf("}, [userScrolled, events.length, seenCount]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd + 45);

    // Must contain the reset call in the else-if branch
    const elseIfPos = effectBody.indexOf("else if (events.length < seenCount)");
    expect(elseIfPos).toBeGreaterThan(-1);

    const afterElseIf = effectBody.slice(elseIfPos);
    expect(afterElseIf).toContain("setSeenCount(events.length)");
  });

  it("seenCount effect dependency array includes seenCount", () => {
    // Without seenCount in deps, the comparison events.length < seenCount
    // would read a stale closure value
    expect(SRC).toContain("[userScrolled, events.length, seenCount]");
  });

  it("seenCount effect still resets to events.length when not scrolled away", () => {
    const effectStart = SRC.indexOf("Track how many events were seen");
    const effectEnd = SRC.indexOf("}, [userScrolled, events.length, seenCount]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd + 45);

    // !userScrolled branch must still be present and set seenCount
    expect(effectBody).toContain("if (!userScrolled)");
    const notScrolledPos = effectBody.indexOf("if (!userScrolled)");
    const afterNotScrolled = effectBody.slice(notScrolledPos);
    // First setSeenCount call should be in the !userScrolled branch
    expect(afterNotScrolled).toContain("setSeenCount(events.length)");
  });

  it("newEventCount formula is Math.max(0, events.length - seenCount)", () => {
    // The formula must still compute the badge count correctly
    expect(SRC).toContain("const newEventCount = Math.max(0, events.length - seenCount)");
  });
});
