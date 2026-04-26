/**
 * Regression test: WorkTree must not apply stale diff fetch results from a prior run.
 *
 * Before the fix, `fetchDiffBodies` and `fetchRunDiff` in the polling effect had no
 * generation guard. When the user rapidly switched runs, an older async fetch could
 * resolve after a newer one and overwrite `repoDiff`/`tmpDiff`/`diffData` with stale
 * data from the previous run, causing the wrong diff to be shown.
 *
 * The fix adds `diffGenRef` (a useRef counter), increments it on each new runId in
 * the initial fetch effect, and checks `gen !== diffGenRef.current` before every
 * `set*` call in both `fetchDiffBodies` and the polling effect.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/worktree/WorkTree.tsx"),
  "utf-8",
);

describe("WorkTree: stale diff fetch guard via generation counter", () => {
  it("declares diffGenRef as a useRef", () => {
    expect(SRC).toContain("diffGenRef = useRef(0)");
  });

  it("initial fetch effect increments diffGenRef", () => {
    expect(SRC).toContain("const gen = ++diffGenRef.current");
  });

  it("fetchDiffBodies accepts a gen parameter", () => {
    // Function signature: (id: string, gen: number)
    expect(SRC).toMatch(/fetchDiffBodies\s*=\s*useCallback\(\s*\(id:\s*string,\s*gen:\s*number\)/);
  });

  it("fetchDiffBodies guards setRepoDiff with generation check", () => {
    const fnStart = SRC.indexOf("const fetchDiffBodies = useCallback");
    const fnEnd = SRC.indexOf("}, []);", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 7);
    expect(fnBody).toContain("if (gen !== diffGenRef.current) return");
    expect(fnBody).toContain("setRepoDiff(");
    expect(fnBody).toContain("setTmpDiff(");
  });

  it("initial fetch effect guards setDiffData in .then with generation check", () => {
    const effectStart = SRC.indexOf("const gen = ++diffGenRef.current");
    const fetchStart = SRC.indexOf("fetchRunDiff(runId)", effectStart);
    // Find the .then callback after this fetchRunDiff call
    const thenStart = SRC.indexOf(".then(", fetchStart);
    const thenEnd = SRC.indexOf(")", thenStart + 6);
    const surroundingBlock = SRC.slice(thenStart, thenStart + 200);
    expect(surroundingBlock).toContain("if (gen !== diffGenRef.current) return");
    expect(surroundingBlock).toContain("setDiffData(");
  });

  it("initial fetch effect passes gen to fetchDiffBodies", () => {
    const effectStart = SRC.indexOf("const gen = ++diffGenRef.current");
    const callStart = SRC.indexOf("fetchDiffBodies(runId, gen)", effectStart);
    expect(callStart).toBeGreaterThan(-1);
  });

  it("polling effect captures gen from diffGenRef.current without incrementing", () => {
    const pollingEffect = SRC.indexOf("const id = setInterval");
    const genCapture = SRC.indexOf("const gen = diffGenRef.current", pollingEffect);
    expect(genCapture).toBeGreaterThan(pollingEffect);
  });

  it("polling effect passes gen to fetchDiffBodies", () => {
    const pollingEffect = SRC.indexOf("const id = setInterval");
    const pollingEnd = SRC.indexOf("return () => clearInterval(id)", pollingEffect);
    const pollingBody = SRC.slice(pollingEffect, pollingEnd);
    expect(pollingBody).toContain("fetchDiffBodies(runId, gen)");
  });

  it("polling effect guards setDiffData with generation check", () => {
    const pollingEffect = SRC.indexOf("const id = setInterval");
    const pollingEnd = SRC.indexOf("return () => clearInterval(id)", pollingEffect);
    const pollingBody = SRC.slice(pollingEffect, pollingEnd);
    expect(pollingBody).toContain("if (gen !== diffGenRef.current) return");
    expect(pollingBody).toContain("setDiffData(");
  });
});
