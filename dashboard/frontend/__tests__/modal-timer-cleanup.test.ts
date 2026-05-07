/**
 * Regression tests: setTimeout in StartRunModal and OnboardingModal must
 * store the timer ID and return a clearTimeout cleanup from the useEffect.
 *
 * Before the fix both modals used:
 *   useEffect(() => { if (open) setTimeout(..., 150); }, [open]);
 * The timer ID was discarded, so if the modal closed within 150ms the
 * callback fired against a stale ref — potentially calling .focus() on
 * an unmounted element and triggering a React warning.
 *
 * The fix stores the timer ID and returns a cleanup function:
 *   useEffect(() => {
 *     if (!open) return;
 *     const timerId = setTimeout(..., 150);
 *     return () => clearTimeout(timerId);
 *   }, [open]);
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const START_MODAL_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
  "utf-8",
);

const ONBOARDING_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/onboarding/OnboardingModal.tsx"),
  "utf-8",
);

describe("StartRunModal: setTimeout clearTimeout cleanup (Bug 3)", () => {
  it("stores the setTimeout return value in a variable", () => {
    expect(START_MODAL_SRC).toContain("const timerId = setTimeout");
  });

  it("returns a cleanup function that calls clearTimeout(timerId)", () => {
    expect(START_MODAL_SRC).toContain("return () => clearTimeout(timerId)");
  });

  it("guards with if (!open) return instead of if (open) { setTimeout }", () => {
    expect(START_MODAL_SRC).toContain("if (!open) return;");
  });

  it("no longer uses the unguarded one-liner setTimeout pattern", () => {
    // The old pattern was: if (open) setTimeout(...); without storing the ID
    const oldPattern = /if \(open\) setTimeout\(/;
    expect(oldPattern.test(START_MODAL_SRC)).toBe(false);
  });

  it("timer delay is 150ms", () => {
    // Verify the delay constant is unchanged
    const timerIdx = START_MODAL_SRC.indexOf("const timerId = setTimeout");
    expect(timerIdx).toBeGreaterThan(-1);
    const snippet = START_MODAL_SRC.slice(timerIdx, timerIdx + 100);
    expect(snippet).toContain("150");
  });
});

describe("OnboardingModal: setTimeout clearTimeout cleanup (Bug 3)", () => {
  it("stores the setTimeout return value in a variable", () => {
    expect(ONBOARDING_SRC).toContain("const timerId = setTimeout");
  });

  it("returns a cleanup function that calls clearTimeout(timerId)", () => {
    expect(ONBOARDING_SRC).toContain("return () => clearTimeout(timerId)");
  });

  it("guards with if (!open) return instead of if (open) { setTimeout }", () => {
    expect(ONBOARDING_SRC).toContain("if (!open) return;");
  });

  it("no longer uses the unguarded one-liner setTimeout pattern", () => {
    // The old pattern was: if (open) setTimeout(...); without storing the ID
    const oldPattern = /if \(open\) setTimeout\(/;
    expect(oldPattern.test(ONBOARDING_SRC)).toBe(false);
  });

  it("timer delay is 150ms", () => {
    const timerIdx = ONBOARDING_SRC.indexOf("const timerId = setTimeout");
    expect(timerIdx).toBeGreaterThan(-1);
    const snippet = ONBOARDING_SRC.slice(timerIdx, timerIdx + 100);
    expect(snippet).toContain("150");
  });

  it("cleanup effect depends on [open, step]", () => {
    // Focus fires on open AND on step change — dep array must include both
    const focusMarker = "// Focus input on step change";
    const focusIdx = ONBOARDING_SRC.indexOf(focusMarker);
    expect(focusIdx).toBeGreaterThan(-1);
    const afterFocus = ONBOARDING_SRC.slice(focusIdx, focusIdx + 300);
    expect(afterFocus).toContain("[open, step]");
  });
});
