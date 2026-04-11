import { describe, it, expect } from "vitest";
import {
  DEFAULT_PHASE_META,
  PHASE_META,
  SUBAGENT_PHASE_MAP,
  hexToRgba,
  resolvePhase,
} from "@/lib/phaseColors";

describe("resolvePhase", () => {
  it("maps code-explorer and debugger to the explore phase", () => {
    expect(resolvePhase("code-explorer").phase).toBe("explore");
    expect(resolvePhase("debugger").phase).toBe("explore");
    expect(resolvePhase("code-explorer").meta).toBe(PHASE_META.explore);
  });

  it("maps architect to the plan phase", () => {
    const result = resolvePhase("architect");
    expect(result.phase).toBe("plan");
    expect(result.meta.color).toBe("#cc88ff");
  });

  it("maps backend-dev and frontend-dev to the build phase", () => {
    expect(resolvePhase("backend-dev").phase).toBe("build");
    expect(resolvePhase("frontend-dev").phase).toBe("build");
  });

  it("maps code-reviewer, ui-reviewer, and security-reviewer to the review phase", () => {
    expect(resolvePhase("code-reviewer").phase).toBe("review");
    expect(resolvePhase("ui-reviewer").phase).toBe("review");
    expect(resolvePhase("security-reviewer").phase).toBe("review");
  });

  it("falls back to DEFAULT_PHASE_META for unknown agent types", () => {
    const result = resolvePhase("made-up-agent");
    expect(result.phase).toBeNull();
    expect(result.meta).toBe(DEFAULT_PHASE_META);
  });

  it("returns null phase but orange color for empty string", () => {
    const result = resolvePhase("");
    expect(result.phase).toBeNull();
    expect(result.meta.color).toBe("#ff8844");
  });
});

describe("PHASE_META color palette", () => {
  it("assigns a unique color to each phase", () => {
    const colors = Object.values(PHASE_META).map((m) => m.color);
    expect(new Set(colors).size).toBe(colors.length);
  });

  it("keeps Review distinct from the running-state amber (#ffaa00)", () => {
    // Regression guard: previously Review == #ffaa00 which collided with
    // the running-state indicator color, making Review cards fully amber
    // with no phase/state separation. Never let it go back.
    expect(PHASE_META.review.color).not.toBe("#ffaa00");
  });
});

describe("SUBAGENT_PHASE_MAP coverage", () => {
  // The source of truth for subagent names is autofyn/prompts/subagents/.
  // If a new subagent is added there without a corresponding map entry,
  // this test won't catch it automatically — but it at least locks the
  // existing set so a silent removal gets flagged.
  it("includes all eight expected subagents", () => {
    const expected = [
      "code-explorer",
      "debugger",
      "architect",
      "backend-dev",
      "frontend-dev",
      "code-reviewer",
      "ui-reviewer",
      "security-reviewer",
    ];
    for (const name of expected) {
      expect(SUBAGENT_PHASE_MAP[name]).toBeDefined();
    }
    expect(Object.keys(SUBAGENT_PHASE_MAP)).toHaveLength(expected.length);
  });
});

describe("hexToRgba", () => {
  it("converts 6-digit hex to rgba with the given alpha", () => {
    expect(hexToRgba("#44ddff", 0.5)).toBe("rgba(68, 221, 255, 0.5)");
    expect(hexToRgba("#000000", 1)).toBe("rgba(0, 0, 0, 1)");
    expect(hexToRgba("#ffffff", 0)).toBe("rgba(255, 255, 255, 0)");
  });

  it("accepts uppercase hex digits", () => {
    expect(hexToRgba("#FFAA00", 0.3)).toBe("rgba(255, 170, 0, 0.3)");
  });

  it("throws on missing # prefix", () => {
    expect(() => hexToRgba("44ddff", 0.5)).toThrow(/invalid hex color/);
  });

  it("throws on 3-digit shorthand", () => {
    expect(() => hexToRgba("#fff", 0.5)).toThrow(/invalid hex color/);
  });

  it("throws on 8-digit hex with alpha channel", () => {
    expect(() => hexToRgba("#44ddff80", 0.5)).toThrow(/invalid hex color/);
  });

  it("throws on non-hex characters", () => {
    expect(() => hexToRgba("#gghhii", 0.5)).toThrow(/invalid hex color/);
  });

  it("throws on alpha outside [0, 1]", () => {
    expect(() => hexToRgba("#44ddff", 1.5)).toThrow(/out of range/);
    expect(() => hexToRgba("#44ddff", -0.1)).toThrow(/out of range/);
  });

  it("works for every phase color without throwing", () => {
    for (const meta of Object.values(PHASE_META)) {
      expect(() => hexToRgba(meta.color, 0.25)).not.toThrow();
    }
    expect(() => hexToRgba(DEFAULT_PHASE_META.color, 0.25)).not.toThrow();
  });
});
