/**
 * Regression tests for bootstrap progress milestone cards.
 *
 * Verifies that run_starting, sandbox_created, and repo_cloned audit events
 * render as milestone cards in the feed, eliminating the 5-10 second UX gap
 * between clicking "Start" and seeing the first run_started event.
 */

import { describe, it, expect } from "vitest";
import { groupEvents } from "@/lib/groupEvents";
import type { FeedEvent } from "@/lib/types";
import { makeAuditEvent } from "./testFactories";

const ts = "2026-04-23T12:00:00Z";

describe("bootstrap progress milestones", () => {
  it("run_starting renders as a milestone with repo detail", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_starting", { repo: "owner/repo" }, ts),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].label).toBe("Run Starting");
      expect(result[0].detail).toBe("owner/repo");
      expect(result[0].color).toBe("#ffaa00");
    }
  });

  it("sandbox_created renders as Sandbox Started milestone", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(2, "sandbox_created", {}, ts),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].label).toBe("Sandbox Started");
      expect(result[0].color).toBe("#88ccff");
    }
  });

  it("repo_cloned renders as a milestone with repo detail", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(3, "repo_cloned", { repo: "owner/repo", branch: "autofyn/fix-abc123" }, ts),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("milestone");
    if (result[0].type === "milestone") {
      expect(result[0].label).toBe("Repo Cloned");
      expect(result[0].detail).toBe("owner/repo");
      expect(result[0].color).toBe("#88ccff");
    }
  });

  it("full bootstrap sequence renders in correct order", () => {
    const t0 = "2026-04-23T12:00:00Z";
    const t1 = "2026-04-23T12:00:02Z";
    const t2 = "2026-04-23T12:00:05Z";
    const t3 = "2026-04-23T12:00:06Z";

    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_starting", { repo: "owner/repo" }, t0),
      makeAuditEvent(2, "sandbox_created", {}, t1),
      makeAuditEvent(3, "repo_cloned", { repo: "owner/repo", branch: "autofyn/fix-abc" }, t2),
      makeAuditEvent(4, "run_started", { model: "claude", branch: "autofyn/fix-abc" }, t3),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(4);

    const labels = result.map((g) => (g.type === "milestone" ? g.label : ""));
    expect(labels).toEqual(["Run Starting", "Sandbox Started", "Repo Cloned", "Run Started"]);
  });

  it("run_starting with empty repo shows empty detail", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "run_starting", {}, ts),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(1);
    if (result[0].type === "milestone") {
      expect(result[0].detail).toBe("");
    }
  });

  it("all sandbox milestones use the same color", () => {
    const sandboxEvents: FeedEvent[] = [
      makeAuditEvent(1, "sandbox_created", {}, ts),
      makeAuditEvent(2, "sandbox_queued", { backend_id: "123" }, ts),
      makeAuditEvent(3, "sandbox_allocated", { backend_id: "123" }, ts),
    ];
    const results = sandboxEvents.map((e) => groupEvents([e])[0]);
    const colors = results.map((r) => (r.type === "milestone" ? r.color : ""));
    expect(new Set(colors).size).toBe(1);
    expect(colors[0]).toBe("#88ccff");
  });

  it("startup_log events are not rendered as milestones", () => {
    const events: FeedEvent[] = [
      makeAuditEvent(1, "startup_log", { line: "srun: job queued" }, ts),
    ];
    const result = groupEvents(events);
    expect(result).toHaveLength(0);
  });
});
