/**
 * Regression tests for EventFeed seenCount drift (BUG 13).
 *
 * Root cause: When events.length decreased (run switch, clear, filter) while
 * the user was scrolled away (userScrolled=true), seenCount was not reset.
 * The subsequent newEventCount calculation: Math.max(0, events.length - seenCount)
 * produced 0 even when new events had arrived, so the FAB showed "Jump to latest"
 * instead of "N new events".
 *
 * Fix: Added an else branch with a functional updater that clamps seenCount
 * down to events.length when it drops. Uses functional updater to avoid
 * needing seenCount in the dependency array (prevents feedback loop).
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/feed/EventFeed.tsx"),
  "utf-8",
);

describe("EventFeed: seenCount reset on events.length drop (BUG 13)", () => {
  it("seenCount effect uses functional updater to clamp on length drop", () => {
    const effectStart = SRC.indexOf("Track how many events were seen");
    expect(effectStart).toBeGreaterThan(-1);

    const effectEnd = SRC.indexOf("}, [userScrolled, events.length]);", effectStart);
    expect(effectEnd).toBeGreaterThan(effectStart);

    const effectBody = SRC.slice(effectStart, effectEnd + 34);
    // Must use functional updater to read prev seenCount without it in deps
    expect(effectBody).toContain("setSeenCount((prev)");
    expect(effectBody).toContain("len < prev");
  });

  it("seenCount effect does NOT include seenCount in dependency array", () => {
    const effectStart = SRC.indexOf("Track how many events were seen");
    const effectEnd = SRC.indexOf("}, [userScrolled, events.length]);", effectStart);
    expect(effectEnd).toBeGreaterThan(effectStart);

    // Dependency array must be exactly [userScrolled, events.length] — no seenCount
    const depArray = SRC.slice(effectEnd, effectEnd + 34);
    expect(depArray).not.toContain("seenCount");
  });

  it("seenCount effect still resets to events.length when not scrolled away", () => {
    const effectStart = SRC.indexOf("Track how many events were seen");
    const effectEnd = SRC.indexOf("}, [userScrolled, events.length]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd + 34);

    // !userScrolled branch must still be present and set seenCount
    expect(effectBody).toContain("if (!userScrolled)");
    const notScrolledPos = effectBody.indexOf("if (!userScrolled)");
    const afterNotScrolled = effectBody.slice(notScrolledPos);
    expect(afterNotScrolled).toContain("setSeenCount(len)");
  });

  it("newEventCount formula is Math.max(0, events.length - seenCount)", () => {
    // The formula must still compute the badge count correctly
    expect(SRC).toContain("const newEventCount = Math.max(0, events.length - seenCount)");
  });
});
