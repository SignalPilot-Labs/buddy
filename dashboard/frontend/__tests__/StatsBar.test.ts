/**
 * StatsBar fail-fast formatter tests.
 *
 * Guards the distinction between "settled", "estimated", and "no data".
 * The previous bug was a `||` chain that masked $0.00 with stale live cost.
 */

import { describe, it, expect } from "vitest";
import { NO_DATA, formatCostStat, formatToolStat, formatContextStat } from "@/components/stats/StatsBar";

describe("formatCostStat", () => {
  it("uses settled value when present (no tilde)", () => {
    expect(formatCostStat(2.5, 0)).toEqual({
      value: "$2.50",
      accent: "text-[#00ff88]",
    });
  });

  it("renders settled $0.00 instead of falling through to live cost", () => {
    // Regression: || would mask $0 with live, ?? was a half-fix.
    expect(formatCostStat(0, 1.23)).toEqual({
      value: "$0.00",
      accent: "text-[#00ff88]",
    });
  });

  it("falls back to live estimate with tilde when settled is null", () => {
    expect(formatCostStat(null, 1.23)).toEqual({
      value: "~$1.23",
      accent: "text-[#00ff88]/70",
    });
  });

  it("renders no-data when both are missing", () => {
    expect(formatCostStat(null, 0)).toEqual({
      value: NO_DATA,
      accent: "text-text-dim",
    });
  });

  it("treats undefined like null", () => {
    expect(formatCostStat(undefined, 0.5).value).toBe("~$0.50");
  });
});

describe("formatToolStat", () => {
  it("uses live count when settled is zero (active run)", () => {
    expect(formatToolStat(0, 5)).toBe("5");
  });

  it("uses live count when settled is null", () => {
    expect(formatToolStat(null, 5)).toBe("5");
  });

  it("renders no-data when both are missing", () => {
    expect(formatToolStat(null, 0)).toBe(NO_DATA);
  });
});

describe("formatContextStat", () => {
  it("formats live tokens with k suffix", () => {
    expect(formatContextStat(2500, null)).toBe("2.5k");
  });

  it("falls back to settled tokens when live is zero", () => {
    expect(formatContextStat(0, 1500)).toBe("1.5k");
  });

  it("renders no-data when both are zero", () => {
    expect(formatContextStat(0, 0)).toBe(NO_DATA);
  });
});
