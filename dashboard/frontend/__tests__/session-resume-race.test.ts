/**
 * Regression test: handleSessionResumed must guard against stale async callbacks.
 *
 * Before the fix, if a user selected a different run while loadRunHistory was
 * in flight, the stale .then() callback would still call sseRef.current.connect()
 * with the old runId — tearing down the new run's SSE connection.
 *
 * The fix mirrors the existing selectGenRef pattern in handleSelectRun: a
 * resumeGenRef generation counter is incremented at entry, captured locally,
 * and checked before any state mutations or connect() calls in the callback.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

describe("handleSessionResumed: race condition guarded by generation counter", () => {
  it("useDashboard declares a resumeGenRef ref", () => {
    expect(SRC).toContain("resumeGenRef");
    expect(SRC).toContain("useRef(0)");
  });

  it("handleSessionResumed increments resumeGenRef at entry", () => {
    const fnStart = SRC.indexOf("handleSessionResumed");
    const fnBlock = SRC.slice(fnStart, SRC.indexOf("handleSelectRun"));
    expect(fnBlock).toContain("resumeGenRef.current");
    expect(fnBlock).toMatch(/\+\+resumeGenRef\.current/);
  });

  it("handleSessionResumed captures gen into a local const", () => {
    const fnStart = SRC.indexOf("handleSessionResumed");
    const fnBlock = SRC.slice(fnStart, SRC.indexOf("handleSelectRun"));
    expect(fnBlock).toMatch(/const gen\s*=/);
  });

  it("handleSessionResumed checks gen before calling sseRef.current.connect in .then()", () => {
    const fnStart = SRC.indexOf("handleSessionResumed");
    const fnBlock = SRC.slice(fnStart, SRC.indexOf("handleSelectRun"));
    const thenStart = fnBlock.indexOf(".then(");
    const thenBlock = fnBlock.slice(thenStart, fnBlock.indexOf(".catch("));
    expect(thenBlock).toContain("gen !== resumeGenRef.current");
  });

  it("handleSessionResumed checks gen before mutating state in .catch()", () => {
    const fnStart = SRC.indexOf("handleSessionResumed");
    const fnBlock = SRC.slice(fnStart, SRC.indexOf("handleSelectRun"));
    const catchStart = fnBlock.indexOf(".catch(");
    const catchBlock = fnBlock.slice(catchStart);
    expect(catchBlock).toContain("gen !== resumeGenRef.current");
  });
});
