/**
 * Regression test: useRuns must not apply stale fetch results after unmount.
 *
 * Before the fix, the useEffect cleanup only called clearInterval(id) but did
 * NOT increment genRef.current. When a component unmounts while a fetchRuns()
 * call is in-flight:
 *   1. refresh() starts, captures gen = 1
 *   2. Component unmounts — cleanup: clearInterval(id) only, genRef.current stays 1
 *   3. fetchRuns() resolves
 *   4. Guard: gen !== genRef.current → 1 !== 1 → FALSE (guard fails!)
 *   5. setRuns(data) and setLoading(false) called on unmounted component
 *
 * The fix adds genRef.current++ to the cleanup so in-flight fetches see a
 * mismatched generation and are discarded.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useRuns.ts"),
  "utf-8",
);

describe("useRuns: genRef incremented on unmount to discard in-flight fetches", () => {
  it("imports useRef", () => {
    expect(SRC).toContain("useRef");
  });

  it("declares genRef as useRef(0)", () => {
    expect(SRC).toContain("genRef = useRef(0)");
  });

  it("refresh captures generation with ++genRef.current before fetch", () => {
    const refreshStart = SRC.indexOf("const refresh = useCallback");
    const refreshEnd = SRC.indexOf("}, [repo]);", refreshStart);
    const refreshBody = SRC.slice(refreshStart, refreshEnd);

    const genIncrPos = refreshBody.indexOf("++genRef.current");
    const fetchPos = refreshBody.indexOf("fetchRuns(");

    expect(genIncrPos).toBeGreaterThan(0);
    expect(fetchPos).toBeGreaterThan(genIncrPos);
  });

  it("refresh guards setRuns with generation check", () => {
    const refreshStart = SRC.indexOf("const refresh = useCallback");
    const refreshEnd = SRC.indexOf("}, [repo]);", refreshStart);
    const refreshBody = SRC.slice(refreshStart, refreshEnd);

    const guardPos = refreshBody.indexOf("if (gen !== genRef.current) return");
    const setRunsPos = refreshBody.indexOf("setRuns(data)");

    expect(guardPos).toBeGreaterThan(0);
    expect(setRunsPos).toBeGreaterThan(guardPos);
  });

  it("effect cleanup increments genRef.current on unmount", () => {
    const effectStart = SRC.indexOf("useEffect(");
    const effectEnd = SRC.indexOf("}, [refresh, pollInterval]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    // The cleanup must increment genRef.current (not just clearInterval)
    expect(effectBody).toContain("genRef.current++");
  });

  it("effect cleanup calls both clearInterval and genRef.current++", () => {
    const effectStart = SRC.indexOf("useEffect(");
    const effectEnd = SRC.indexOf("}, [refresh, pollInterval]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    // Both must be present in the return cleanup
    const returnPos = effectBody.lastIndexOf("return () =>");
    const cleanupBlock = effectBody.slice(returnPos);

    expect(cleanupBlock).toContain("clearInterval(id)");
    expect(cleanupBlock).toContain("genRef.current++");
  });

  it("effect cleanup has genRef.current++ after clearInterval", () => {
    const effectStart = SRC.indexOf("useEffect(");
    const effectEnd = SRC.indexOf("}, [refresh, pollInterval]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    const returnPos = effectBody.lastIndexOf("return () =>");
    const cleanupBlock = effectBody.slice(returnPos);

    const clearPos = cleanupBlock.indexOf("clearInterval(id)");
    const incrPos = cleanupBlock.indexOf("genRef.current++");

    expect(clearPos).toBeGreaterThan(0);
    expect(incrPos).toBeGreaterThan(clearPos);
  });
});
