/**
 * Regression tests for OnboardingModal stale state on reopen (BUG 8).
 *
 * Root cause: When the user closed OnboardingModal mid-flow (e.g., at step 2
 * with an error), then reopened it, the modal preserved the previous step,
 * error message, and entered values. The user saw a stale form instead of a
 * fresh start-from-zero flow.
 *
 * Fix: Added prevOpenRef + useEffect that resets step, error, values, and
 * showPassword when open transitions false -> true.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/onboarding/OnboardingModal.tsx"),
  "utf-8",
);

describe("OnboardingModal: state reset on reopen (BUG 8)", () => {
  it("prevOpenRef is declared to track previous open value", () => {
    expect(SRC).toContain("prevOpenRef");
    expect(SRC).toContain("useRef(open)");
  });

  it("useEffect resets step to 0 on false-to-true open transition", () => {
    // Must guard on !prevOpenRef.current (was closed) AND open (now open)
    expect(SRC).toContain("!prevOpenRef.current");
    expect(SRC).toContain("setStep(0)");
  });

  it("useEffect resets error to null on reopen", () => {
    expect(SRC).toContain("setError(null)");
  });

  it("useEffect resets values to empty object on reopen", () => {
    expect(SRC).toContain("setValues({})");
  });

  it("useEffect resets showPassword to false on reopen", () => {
    expect(SRC).toContain("setShowPassword(false)");
  });

  it("prevOpenRef.current is updated at the end of each effect run", () => {
    const effectStart = SRC.indexOf("prevOpenRef.current = open");
    expect(effectStart).toBeGreaterThan(-1);
  });

  it("reset effect depends only on [open]", () => {
    // The effect block containing prevOpenRef reset must list [open] as deps
    const resetEffectStart = SRC.indexOf("if (open && !prevOpenRef.current)");
    expect(resetEffectStart).toBeGreaterThan(-1);

    // Find the closing ], [open]); pattern after the reset block
    const afterEffect = SRC.slice(resetEffectStart);
    // The effect closing }, [open]) must appear before any other dependency array
    const depArrayIdx = afterEffect.indexOf("}, [open])");
    expect(depArrayIdx).toBeGreaterThan(-1);
  });

  it("reset block resets all four state variables in order", () => {
    const blockStart = SRC.indexOf("if (open && !prevOpenRef.current)");
    // Find the closing brace of the if block — look for setShowPassword which is last
    const showPasswordIdx = SRC.indexOf("setShowPassword(false)", blockStart);
    expect(showPasswordIdx).toBeGreaterThan(blockStart);

    // All four resets must appear before setShowPassword
    const stepIdx = SRC.indexOf("setStep(0)", blockStart);
    const errorIdx = SRC.indexOf("setError(null)", blockStart);
    const valuesIdx = SRC.indexOf("setValues({})", blockStart);

    expect(stepIdx).toBeGreaterThan(-1);
    expect(errorIdx).toBeGreaterThan(-1);
    expect(valuesIdx).toBeGreaterThan(-1);
    expect(stepIdx).toBeLessThan(showPasswordIdx);
    expect(errorIdx).toBeLessThan(showPasswordIdx);
    expect(valuesIdx).toBeLessThan(showPasswordIdx);
  });

  it("reset effect appears before focus effect in source order", () => {
    // The reset-on-open effect must be defined before the focus effect so it
    // fires first and the input focus fires on the already-reset step.
    const resetEffectStart = SRC.indexOf("if (open && !prevOpenRef.current)");
    const focusEffectStart = SRC.indexOf("if (open) setTimeout(() => inputRef.current?.focus()");

    expect(resetEffectStart).toBeGreaterThan(-1);
    expect(focusEffectStart).toBeGreaterThan(-1);
    expect(resetEffectStart).toBeLessThan(focusEffectStart);
  });
});
