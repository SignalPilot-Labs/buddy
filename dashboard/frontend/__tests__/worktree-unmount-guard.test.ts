/**
 * Regression test: WorkTree must not apply stale fetch results after unmount.
 *
 * Before the fix, the first useEffect (deps: [runId]) incremented
 * diffGenRef.current at the START of the effect but did NOT return a cleanup
 * function to increment it on unmount. When a component unmounts while
 * fetchRunDiff() or fetchDiffBodies() is in-flight:
 *   1. runId changes → gen = ++diffGenRef.current → gen = 1
 *   2. Component unmounts — no cleanup, diffGenRef.current stays 1
 *   3. fetchRunDiff() resolves
 *   4. Guard: gen !== diffGenRef.current → 1 !== 1 → FALSE (guard fails!)
 *   5. setDiffData() / setRepoDiff() called on unmounted component
 *
 * The fix adds `return () => { diffGenRef.current++; };` at the end of the
 * effect body (after the async fetch calls), so in-flight fetches see a
 * mismatched generation and are discarded.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/worktree/WorkTree.tsx"),
  "utf-8",
);

describe("WorkTree: diffGenRef incremented on unmount to discard in-flight fetches", () => {
  it("declares diffGenRef as useRef(0)", () => {
    expect(SRC).toContain("diffGenRef = useRef(0)");
  });

  it("first effect increments diffGenRef.current before fetch", () => {
    // Find the first useEffect block (the one with [runId] dep)
    const effectStart = SRC.indexOf("useEffect(() => {");
    const effectEnd = SRC.indexOf("}, [runId]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    expect(effectBody).toContain("++diffGenRef.current");
  });

  it("effect cleanup increments diffGenRef.current on unmount", () => {
    const effectStart = SRC.indexOf("useEffect(() => {");
    const effectEnd = SRC.indexOf("}, [runId]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    // The cleanup must increment diffGenRef.current
    expect(effectBody).toContain("diffGenRef.current++");
  });

  it("effect cleanup returns arrow function with increment", () => {
    const effectStart = SRC.indexOf("useEffect(() => {");
    const effectEnd = SRC.indexOf("}, [runId]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    // Must return a cleanup function that increments the generation counter
    expect(effectBody).toContain("return () => { diffGenRef.current++; }");
  });

  it("early return path for null runId does not have cleanup increment", () => {
    const effectStart = SRC.indexOf("useEffect(() => {");
    const effectEnd = SRC.indexOf("}, [runId]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    // The early return when !runId should be a bare `return;` (no async started)
    const nullGuardBlock = effectBody.slice(
      effectBody.indexOf("if (!runId)"),
      effectBody.indexOf("return;") + "return;".length,
    );

    expect(nullGuardBlock).not.toContain("diffGenRef.current++");
  });

  it("fetchDiffBodies call is guarded by gen !== diffGenRef.current inside the callback", () => {
    // fetchDiffBodies captures gen and guards setState with the generation check
    const fetchBodiesStart = SRC.indexOf("const fetchDiffBodies = useCallback");
    const fetchBodiesEnd = SRC.indexOf("}, []);", fetchBodiesStart);
    const fetchBodiesBody = SRC.slice(fetchBodiesStart, fetchBodiesEnd);

    expect(fetchBodiesBody).toContain("if (gen !== diffGenRef.current) return");
  });
});
