import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { timeAgo, formatCost, formatTokens, elapsed } from "@/lib/format";

// ---------------------------------------------------------------------------
// timeAgo
// ---------------------------------------------------------------------------
describe("timeAgo", () => {
  it('returns "Xs ago" for recent dates (less than 60 seconds)', () => {
    const now = new Date();
    const tenSecsAgo = new Date(now.getTime() - 10_000).toISOString();
    expect(timeAgo(tenSecsAgo)).toBe("10s ago");
  });

  it('returns "Xm ago" for dates a few minutes ago', () => {
    const fiveMinsAgo = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(timeAgo(fiveMinsAgo)).toBe("5m ago");
  });

  it('returns "Xh ago" for dates a few hours ago', () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3_600_000).toISOString();
    expect(timeAgo(threeHoursAgo)).toBe("3h ago");
  });

  it('returns "Xd ago" for dates days ago', () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 86_400_000).toISOString();
    expect(timeAgo(twoDaysAgo)).toBe("2d ago");
  });
});

// ---------------------------------------------------------------------------
// formatCost
// ---------------------------------------------------------------------------
describe("formatCost", () => {
  it("returns empty string for null", () => {
    expect(formatCost(null)).toBe("");
  });

  it("returns empty string for 0", () => {
    expect(formatCost(0)).toBe("");
  });

  it("formats a positive cost with $ prefix and two decimal places", () => {
    expect(formatCost(1.5)).toBe("$1.50");
  });

  it("formats a larger cost correctly", () => {
    expect(formatCost(12.345)).toBe("$12.35");
  });
});

// ---------------------------------------------------------------------------
// formatTokens
// ---------------------------------------------------------------------------
describe("formatTokens", () => {
  it("returns '0' for null", () => {
    expect(formatTokens(null)).toBe("0");
  });

  it("returns '0' for 0", () => {
    expect(formatTokens(0)).toBe("0");
  });

  it("returns the number as a string for values below 1 000", () => {
    expect(formatTokens(999)).toBe("999");
  });

  it("returns '1k' for 1 000", () => {
    expect(formatTokens(1_000)).toBe("1k");
  });

  it("returns '1.5k' for 1 500", () => {
    expect(formatTokens(1_500)).toBe("1.5k");
  });

  it("returns '1M' for 1 000 000", () => {
    expect(formatTokens(1_000_000)).toBe("1.0M");
  });

  it("returns '1.5M' for 1 500 000", () => {
    expect(formatTokens(1_500_000)).toBe("1.5M");
  });
});

// ---------------------------------------------------------------------------
// elapsed
// ---------------------------------------------------------------------------
describe("elapsed", () => {
  let nowSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Fix Date.now() so tests are deterministic
    nowSpy = vi.spyOn(Date, "now");
  });

  afterEach(() => {
    nowSpy.mockRestore();
  });

  it('returns "Xs" for 30 seconds ago', () => {
    const base = 1_700_000_000; // arbitrary unix timestamp (seconds)
    nowSpy.mockReturnValue((base + 30) * 1000);
    expect(elapsed(base)).toBe("30s");
  });

  it('returns "Xm" for 5 minutes ago', () => {
    const base = 1_700_000_000;
    nowSpy.mockReturnValue((base + 5 * 60) * 1000);
    expect(elapsed(base)).toBe("5m");
  });

  it('returns "Xh Ym" for 2 hours 15 minutes ago', () => {
    const base = 1_700_000_000;
    const secondsAgo = 2 * 3600 + 15 * 60;
    nowSpy.mockReturnValue((base + secondsAgo) * 1000);
    expect(elapsed(base)).toBe("2h 15m");
  });
});
