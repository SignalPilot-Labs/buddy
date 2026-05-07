/**
 * Regression test: useNetworkInfo must not apply stale fetch results after
 * unmount or when a newer fetch has already started (e.g., React strict mode
 * double-mount).
 *
 * Before the fix, refresh() awaited fetchNetworkInfo() then immediately called
 * setUrl(info.url) with no guard. If the component unmounted during the fetch,
 * setUrl would be called on an unmounted component; in strict mode double-mount,
 * the first (stale) fetch could overwrite the second (fresh) fetch.
 *
 * The fix adds a genRef (useRef counter) that is incremented before the await
 * and checked after — stale results are discarded if gen !== genRef.current.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useNetworkInfo.ts"),
  "utf-8",
);

describe("useNetworkInfo: stale fetch guard via generation counter", () => {
  it("imports useRef", () => {
    expect(SRC).toContain("useRef");
  });

  it("declares genRef as a useRef(0)", () => {
    expect(SRC).toContain("genRef = useRef(0)");
  });

  it("increments genRef before the await in refresh()", () => {
    const refreshStart = SRC.indexOf("const refresh = useCallback");
    const refreshEnd = SRC.indexOf("}, []);", refreshStart);
    const refreshBody = SRC.slice(refreshStart, refreshEnd);

    const genIncrPos = refreshBody.indexOf("++genRef.current");
    const awaitPos = refreshBody.indexOf("await ");

    expect(genIncrPos).toBeGreaterThan(0);
    expect(awaitPos).toBeGreaterThan(genIncrPos);
  });

  it("checks gen against genRef.current after the await", () => {
    const refreshStart = SRC.indexOf("const refresh = useCallback");
    const refreshEnd = SRC.indexOf("}, []);", refreshStart);
    const refreshBody = SRC.slice(refreshStart, refreshEnd);

    const awaitPos = refreshBody.indexOf("await ");
    const guardPos = refreshBody.indexOf("if (gen !== genRef.current) return");

    expect(guardPos).toBeGreaterThan(awaitPos);
  });

  it("setUrl is called only after the generation guard", () => {
    const refreshStart = SRC.indexOf("const refresh = useCallback");
    const refreshEnd = SRC.indexOf("}, []);", refreshStart);
    const refreshBody = SRC.slice(refreshStart, refreshEnd);

    const guardPos = refreshBody.indexOf("if (gen !== genRef.current) return");
    const setUrlPos = refreshBody.indexOf("setUrl(");

    expect(guardPos).toBeGreaterThan(0);
    expect(setUrlPos).toBeGreaterThan(guardPos);
  });

  it("guard appears exactly once in refresh() — no silent stale paths", () => {
    const refreshStart = SRC.indexOf("const refresh = useCallback");
    const refreshEnd = SRC.indexOf("}, []);", refreshStart);
    const refreshBody = SRC.slice(refreshStart, refreshEnd);

    const guards = (refreshBody.match(/gen !== genRef\.current/g) ?? []).length;
    expect(guards).toBe(1);
  });

  it("useEffect still sets up poll interval and clears it on cleanup", () => {
    const effectStart = SRC.indexOf("useEffect(");
    const effectEnd = SRC.indexOf("}, [refresh]);", effectStart);
    const effectBody = SRC.slice(effectStart, effectEnd);

    expect(effectBody).toContain("setInterval");
    expect(effectBody).toContain("clearInterval");
    expect(effectBody).toContain("return ()");
  });
});
