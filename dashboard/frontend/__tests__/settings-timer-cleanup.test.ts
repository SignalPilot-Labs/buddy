/**
 * Regression test: Settings page must clean up savedTimerRef on unmount.
 *
 * Before the fix, `savedTimerRef` stored a `setTimeout` handle set in
 * `handleSave` but there was no cleanup on unmount. If the user clicked
 * Save and navigated away within 2 seconds, the timer would fire
 * `setSaved(false)` on an unmounted component — a memory leak and React
 * warning.
 *
 * The fix adds a `useEffect` with empty deps `[]` whose cleanup function
 * calls `clearTimeout(savedTimerRef.current)`.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../app/settings/page.tsx"),
  "utf-8",
);

describe("Settings: savedTimerRef cleanup on unmount", () => {
  it("has a useEffect that references savedTimerRef in its cleanup", () => {
    // Find all useEffect blocks and check at least one cleanup function
    // references clearTimeout with savedTimerRef
    expect(SRC).toContain("clearTimeout(savedTimerRef.current)");
  });

  it("cleanup useEffect has empty dependency array", () => {
    // The cleanup effect must use [] deps so it only runs on unmount
    const cleanupIdx = SRC.indexOf("clearTimeout(savedTimerRef.current)");
    expect(cleanupIdx).toBeGreaterThan(-1);
    // Find the useEffect that wraps this cleanup — look backward for useEffect
    const before = SRC.slice(0, cleanupIdx);
    const effectStart = before.lastIndexOf("useEffect(");
    // Extend the slice far enough to capture the closing `, [])` after the effect body
    const effectBlock = SRC.slice(effectStart, cleanupIdx + 200);
    expect(effectBlock).toContain("}, [])");
  });

  it("savedTimerRef is declared before the cleanup useEffect", () => {
    const timerRefIdx = SRC.indexOf("const savedTimerRef = useRef");
    const cleanupIdx = SRC.indexOf("clearTimeout(savedTimerRef.current)");
    expect(timerRefIdx).toBeGreaterThan(-1);
    expect(cleanupIdx).toBeGreaterThan(timerRefIdx);
  });

  it("handleSave still sets savedTimerRef.current on success", () => {
    expect(SRC).toContain("savedTimerRef.current = setTimeout");
  });
});
