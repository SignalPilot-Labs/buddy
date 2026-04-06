/**
 * Run status transition tests.
 *
 * Verifies that STATUS_META covers all statuses, that status transitions
 * produce correct UI labels, and that edge cases don't crash.
 */

import { describe, it, expect } from "vitest";
import { STATUS_META } from "@/lib/types";
import type { RunStatus } from "@/lib/types";

const ALL_STATUSES: RunStatus[] = [
  "starting", "running", "paused", "stopped",
  "completed", "error", "crashed", "killed", "rate_limited",
];

describe("STATUS_META coverage", () => {
  it("has an entry for every RunStatus", () => {
    ALL_STATUSES.forEach((status) => {
      const meta = STATUS_META[status];
      expect(meta).toBeDefined();
      expect(meta.label).toBeTruthy();
      expect(meta.color).toBeTruthy();
      expect(meta.dot).toBeTruthy();
    });
  });

  it("starting status has pulse animation", () => {
    expect(STATUS_META.starting.pulse).toBe(true);
  });

  it("running status has pulse animation", () => {
    expect(STATUS_META.running.pulse).toBe(true);
  });

  it("completed status does not pulse", () => {
    expect(STATUS_META.completed.pulse).toBe(false);
  });

  it("crashed status does not pulse", () => {
    expect(STATUS_META.crashed.pulse).toBe(false);
  });
});

describe("Status labels", () => {
  it("starting shows Starting label", () => {
    expect(STATUS_META.starting.label).toBe("Starting");
  });

  it("rate_limited shows Rate Limited label", () => {
    expect(STATUS_META.rate_limited.label).toMatch(/rate.?limit/i);
  });
});
