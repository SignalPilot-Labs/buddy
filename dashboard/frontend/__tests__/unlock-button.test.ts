/**
 * Unlock button visibility tests.
 *
 * The unlock button should only appear when run_unlocked === false
 * (i.e. the session has a time lock that hasn't been unlocked).
 * It must NOT appear for sessions with no time lock (run_unlocked is
 * null/undefined) or already-unlocked sessions (run_unlocked is true).
 */

import { describe, it, expect } from "vitest";

/**
 * Mirrors the sessionLocked derivation in page.tsx:
 *   sessionLocked={activeRunHealth?.run_unlocked === false}
 */
function isSessionLocked(sessionUnlocked: boolean | null | undefined): boolean {
  return sessionUnlocked === false;
}

describe("Unlock button visibility", () => {
  it("shows unlock when session is locked (run_unlocked=false)", () => {
    expect(isSessionLocked(false)).toBe(true);
  });

  it("hides unlock when session is unlocked (run_unlocked=true)", () => {
    expect(isSessionLocked(true)).toBe(false);
  });

  it("hides unlock when no time lock exists (run_unlocked=null)", () => {
    expect(isSessionLocked(null)).toBe(false);
  });

  it("hides unlock when no time lock exists (run_unlocked=undefined)", () => {
    expect(isSessionLocked(undefined)).toBe(false);
  });

  it("hides unlock when health data is missing", () => {
    // Mirrors: activeRunHealth?.run_unlocked === false
    // When activeRunHealth is undefined, optional chaining yields undefined, not false.
    expect(isSessionLocked(undefined)).toBe(false);
  });
});
