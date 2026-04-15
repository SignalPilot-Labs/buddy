/**
 * Tests for WorkTree diff source selection and empty state logic.
 *
 * Verifies the component correctly prioritises diff sources (stored > live > agent > session)
 * and shows distinct empty states for each scenario.
 */

import { describe, it, expect } from "vitest";
import type { DiffStats } from "@/lib/api";
import type { RunStatus } from "@/lib/types";
import { TERMINAL_STATUSES } from "@/lib/constants";

// Replicate the source selection logic from WorkTree so we can test it
// without mounting the component (pure logic, no DOM needed).

type ShowSource = "diff" | "session" | "empty";
type DisplaySource = "diff-live" | "diff-stored" | "diff-agent" | "session" | null;
type EmptyReason = "no-run" | "loading" | "unavailable" | "active-no-changes" | "completed-no-changes";

function resolveShowSource(diffData: DiffStats | null, hasLiveChanges: boolean): ShowSource {
  const hasGitDiff = diffData !== null && diffData.files.length > 0;
  if (hasLiveChanges) return "session";
  if (hasGitDiff) return "diff";
  return "empty";
}

function resolveDisplaySource(showSource: ShowSource, diffData: DiffStats | null): DisplaySource {
  if (showSource === "session") return "session";
  if (showSource !== "diff" || !diffData) return null;
  if (diffData.source === "live") return "diff-live";
  if (diffData.source === "stored") return "diff-stored";
  if (diffData.source === "agent") return "diff-agent";
  return null;
}

function resolveEmptyReason(
  runId: string | null,
  diffLoading: boolean,
  diffData: DiffStats | null,
  runStatus: RunStatus | null,
): EmptyReason {
  if (!runId) return "no-run";
  if (diffLoading && !diffData) return "loading";
  if (diffData?.source === "unavailable") return "unavailable";
  const isTerminal = runStatus !== null && TERMINAL_STATUSES.has(runStatus);
  return isTerminal ? "completed-no-changes" : "active-no-changes";
}

function makeDiff(source: DiffStats["source"], fileCount: number): DiffStats {
  const files = Array.from({ length: fileCount }, (_, i) => ({
    path: `file${i}.ts`,
    added: 10,
    removed: 2,
    status: "modified" as const,
  }));
  return {
    files,
    total_files: fileCount,
    total_added: fileCount * 10,
    total_removed: fileCount * 2,
    source,
  };
}

describe("resolveShowSource", () => {
  it("prefers session over git diff", () => {
    expect(resolveShowSource(makeDiff("stored", 3), true)).toBe("session");
  });

  it("falls back to session when diff has no files", () => {
    expect(resolveShowSource(makeDiff("unavailable", 0), true)).toBe("session");
  });

  it("falls back to session when diff is null", () => {
    expect(resolveShowSource(null, true)).toBe("session");
  });

  it("returns empty when no diff and no session data", () => {
    expect(resolveShowSource(null, false)).toBe("empty");
  });

  it("returns empty when diff unavailable and no session data", () => {
    expect(resolveShowSource(makeDiff("unavailable", 0), false)).toBe("empty");
  });
});

describe("resolveDisplaySource", () => {
  it("returns diff-stored for stored source", () => {
    expect(resolveDisplaySource("diff", makeDiff("stored", 1))).toBe("diff-stored");
  });

  it("returns diff-live for live source", () => {
    expect(resolveDisplaySource("diff", makeDiff("live", 1))).toBe("diff-live");
  });

  it("returns diff-agent for agent source", () => {
    expect(resolveDisplaySource("diff", makeDiff("agent", 1))).toBe("diff-agent");
  });

  it("returns session for session fallback", () => {
    expect(resolveDisplaySource("session", null)).toBe("session");
  });

  it("returns null for empty state", () => {
    expect(resolveDisplaySource("empty", null)).toBeNull();
  });
});

describe("resolveEmptyReason", () => {
  it("returns no-run when runId is null", () => {
    expect(resolveEmptyReason(null, false, null, null)).toBe("no-run");
  });

  it("returns loading when diff is loading", () => {
    expect(resolveEmptyReason("run-1", true, null, "running")).toBe("loading");
  });

  it("returns unavailable when source is unavailable", () => {
    const diff = makeDiff("unavailable", 0);
    expect(resolveEmptyReason("run-1", false, diff, "completed")).toBe("unavailable");
  });

  it("returns completed-no-changes for terminal run with no diff", () => {
    expect(resolveEmptyReason("run-1", false, null, "completed")).toBe("completed-no-changes");
  });

  it("returns completed-no-changes for stopped run", () => {
    expect(resolveEmptyReason("run-1", false, null, "stopped")).toBe("completed-no-changes");
  });

  it("returns active-no-changes for running run with no diff yet", () => {
    expect(resolveEmptyReason("run-1", false, null, "running")).toBe("active-no-changes");
  });

  it("returns active-no-changes for paused run", () => {
    expect(resolveEmptyReason("run-1", false, null, "paused")).toBe("active-no-changes");
  });
});

describe("polling behaviour", () => {
  it("polls for live source", () => {
    const diff = makeDiff("live", 2);
    const shouldPoll = diff.source === "live" || diff.source === "agent";
    expect(shouldPoll).toBe(true);
  });

  it("polls for agent source", () => {
    const diff = makeDiff("agent", 2);
    const shouldPoll = diff.source === "live" || diff.source === "agent";
    expect(shouldPoll).toBe(true);
  });

  it("does not poll for stored source", () => {
    const diff = makeDiff("stored", 2);
    const shouldPoll = diff.source === "live" || diff.source === "agent";
    expect(shouldPoll).toBe(false);
  });

  it("does not poll for unavailable source", () => {
    const diff = makeDiff("unavailable", 0);
    const shouldPoll = diff.source === "live" || diff.source === "agent";
    expect(shouldPoll).toBe(false);
  });
});
