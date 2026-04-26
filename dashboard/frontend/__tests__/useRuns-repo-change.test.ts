/**
 * Regression test: useRuns must clear stale runs immediately when repo changes.
 *
 * Before the fix, when the `repo` filter changed, setLoading(true) was called
 * and refresh() fetched new data — but the old repo's runs array stayed in
 * state until the fetch completed. The sidebar briefly showed runs from the
 * wrong repo.
 *
 * The fix adds setRuns([]) right after setLoading(true) in the useEffect,
 * so consumers see an empty list during the fetch rather than stale wrong-repo
 * data. The existing genRef guard already discards stale fetch results if the
 * repo changes again during the fetch.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useRuns.ts"),
  "utf-8",
);

describe("useRuns: stale runs cleared immediately on repo filter change", () => {
  it("useEffect calls setRuns([]) after setLoading(true)", () => {
    const effectStart = SRC.indexOf("useEffect(");
    const effectEnd = SRC.indexOf("}, [refresh, pollInterval])");
    const effectBlock = SRC.slice(effectStart, effectEnd);

    expect(effectBlock).toContain("setLoading(true)");
    expect(effectBlock).toContain("setRuns([])");

    const loadingIdx = effectBlock.indexOf("setLoading(true)");
    const clearIdx = effectBlock.indexOf("setRuns([])");

    // setRuns([]) must come after setLoading(true)
    expect(clearIdx).toBeGreaterThan(loadingIdx);
  });

  it("setRuns([]) appears before the refresh() call in the effect", () => {
    const effectStart = SRC.indexOf("useEffect(");
    const effectEnd = SRC.indexOf("}, [refresh, pollInterval])");
    const effectBlock = SRC.slice(effectStart, effectEnd);

    const clearIdx = effectBlock.indexOf("setRuns([])");
    const refreshIdx = effectBlock.indexOf("refresh()");

    // Clear stale data before triggering the new fetch
    expect(clearIdx).toBeLessThan(refreshIdx);
  });

  it("genRef guard still discards fetches that arrive after repo changes again", () => {
    const refreshStart = SRC.indexOf("const refresh = useCallback");
    const refreshEnd = SRC.indexOf("}, [repo])");
    const refreshBlock = SRC.slice(refreshStart, refreshEnd);

    // The generation counter check must still be present
    expect(refreshBlock).toContain("genRef.current");
    expect(refreshBlock).toContain("gen !== genRef.current");
  });
});
