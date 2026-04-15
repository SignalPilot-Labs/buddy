/**
 * Resume flow regression tests.
 *
 * Verifies that all resume code paths go through handleRestart,
 * which disconnects SSE, resets cursors, and reconnects. Prevents
 * regressions where resume bypasses SSE reconnection and events
 * stop showing until page refresh.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const PAGE_SRC = fs.readFileSync(
  path.resolve(__dirname, "../app/page.tsx"),
  "utf-8",
);

const USE_RUN_ACTIONS_SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useRunActions.ts"),
  "utf-8",
);

const USE_SSE_SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useSSE.ts"),
  "utf-8",
);

describe("resume flow: all paths use handleRestart", () => {
  it("page.tsx does not call resumeAgent directly", () => {
    // resumeAgent should only be called inside useRunActions, never in page.tsx
    expect(PAGE_SRC).not.toContain("resumeAgent");
  });

  it("page.tsx does not import resumeAgent", () => {
    // If it's not called, it shouldn't be imported
    const importLine = PAGE_SRC.split("\n").find((l) => l.includes("from") && l.includes("api"));
    expect(importLine).not.toContain("resumeAgent");
  });

  it("desktop onResume calls handleRestart", () => {
    expect(PAGE_SRC).toContain("onResume={(prompt) => handleRestart(prompt)");
  });

  it("mobile onResume calls handleRestart", () => {
    // All onResume props should use handleRestart, not toastControlAction
    const resumeLines = PAGE_SRC.split("\n").filter((l) => l.includes("onResume"));
    for (const line of resumeLines) {
      expect(line).not.toContain("toastControlAction");
      expect(line).toContain("handleRestart");
    }
  });
});

describe("resume flow: SSE cursor reset", () => {
  it("handleRestart resets cursors to -1 before reconnect", () => {
    expect(USE_RUN_ACTIONS_SRC).toContain("afterTool: -1, afterAudit: -1");
  });

  it("handleRestart calls refreshRunsRef after resume", () => {
    // Must refresh run list so status card updates
    const restartBlock = USE_RUN_ACTIONS_SRC.slice(
      USE_RUN_ACTIONS_SRC.indexOf("handleRestart"),
    );
    expect(restartBlock).toContain("refreshRunsRef.current()");
  });

  it("handleRestart accepts optional prompt", () => {
    expect(USE_RUN_ACTIONS_SRC).toContain("(prompt?: string)");
  });
});

describe("polling cursor sync", () => {
  it("polling updates lastToolCursorRef when tool events arrive", () => {
    // Polling must sync cursors to refs so reconnect doesn't use stale values
    expect(USE_SSE_SRC).toContain("lastToolCursorRef.current = afterTool");
  });

  it("polling updates lastAuditCursorRef when audit events arrive", () => {
    expect(USE_SSE_SRC).toContain("lastAuditCursorRef.current = afterAudit");
  });
});
