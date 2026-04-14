/**
 * Agent run card status derivation tests.
 *
 * Verifies the boolean logic that determines whether an agent subagent card
 * shows as "running", "paused", "completed", or "failed". Mirrors the logic
 * in AgentRunCard.tsx lines 55-59.
 *
 * Key invariant: a subagent must NOT show "failed" while the run is still
 * active — it should show "running" instead (the subagent is just waiting
 * for its turn after an inject or between tool calls).
 */

import { describe, it, expect } from "vitest";

/**
 * Pure derivation of agent card status flags, extracted from AgentRunCard.tsx.
 */
function deriveStatus(runActive: boolean, runPaused: boolean, phase: string, hasOutput: boolean) {
  const isPending = runActive && !runPaused && phase === "pre" && !hasOutput;
  const isPaused = runActive && runPaused && phase === "pre" && !hasOutput;
  const isCompleted = !isPending && !!hasOutput;
  const isFailed = !runActive && !isPending && !isPaused && phase === "pre" && !hasOutput;
  return { isPending, isPaused, isCompleted, isFailed };
}

describe("Agent run card status derivation", () => {
  it("shows running when run is active and subagent has no output yet", () => {
    const s = deriveStatus(true, false, "pre", false);
    expect(s.isPending).toBe(true);
    expect(s.isFailed).toBe(false);
  });

  it("shows paused when run is active and paused", () => {
    const s = deriveStatus(true, true, "pre", false);
    expect(s.isPaused).toBe(true);
    expect(s.isPending).toBe(false);
    expect(s.isFailed).toBe(false);
  });

  it("shows completed when output data exists", () => {
    const s = deriveStatus(false, false, "post", true);
    expect(s.isCompleted).toBe(true);
    expect(s.isFailed).toBe(false);
    expect(s.isPending).toBe(false);
  });

  it("shows completed when run is active and output exists", () => {
    const s = deriveStatus(true, false, "post", true);
    expect(s.isCompleted).toBe(true);
    expect(s.isFailed).toBe(false);
  });

  it("shows failed only when run is NOT active and no output", () => {
    const s = deriveStatus(false, false, "pre", false);
    expect(s.isFailed).toBe(true);
    expect(s.isPending).toBe(false);
    expect(s.isCompleted).toBe(false);
  });

  it("does NOT show failed when run is active — the key regression case", () => {
    // This is the inject bug: run is active, subagent is mid-task (pre, no output).
    // Must show running, not failed.
    const s = deriveStatus(true, false, "pre", false);
    expect(s.isFailed).toBe(false);
    expect(s.isPending).toBe(true);
  });

  it("does NOT show failed when run is active and paused", () => {
    const s = deriveStatus(true, true, "pre", false);
    expect(s.isFailed).toBe(false);
    expect(s.isPaused).toBe(true);
  });

  it("shows no status flags when run ended with output", () => {
    const s = deriveStatus(false, false, "post", true);
    expect(s.isPending).toBe(false);
    expect(s.isPaused).toBe(false);
    expect(s.isFailed).toBe(false);
    expect(s.isCompleted).toBe(true);
  });
});
