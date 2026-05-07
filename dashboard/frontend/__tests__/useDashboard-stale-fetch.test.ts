/**
 * Regression test: useDashboard must not apply stale fetch results after
 * unmount or when a newer fetch has already started (e.g., React strict mode
 * double-mount, rapid repo switches).
 *
 * Before the fix, the initial useEffect called fetchSettingsStatus().then(...)
 * and fetchRepos().then(...) without any guard. If the component unmounted
 * before these promises resolved, the .then() callbacks would call state setters
 * on an unmounted component. Similarly, handleRepoSwitch called
 * fetchRepos().then(setRepos) with no guard.
 *
 * The fix adds an initGenRef (useRef counter) that is incremented before
 * each fetch and checked in the .then() callbacks — stale results are
 * discarded if gen !== initGenRef.current. A cleanup function in the initial
 * effect also increments the ref to invalidate in-flight fetches on unmount.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

describe("useDashboard: stale fetch guard via initGenRef generation counter", () => {
  it("imports useRef", () => {
    expect(SRC).toContain("useRef");
  });

  it("declares initGenRef as useRef(0)", () => {
    expect(SRC).toContain("initGenRef = useRef(0)");
  });

  it("initial effect captures generation before fetches", () => {
    // Find the useEffect block that contains fetchSettingsStatus
    const effectStart = SRC.indexOf("fetchSettingsStatus().then");
    const blockStart = SRC.lastIndexOf("useEffect(", effectStart);
    const blockEnd = SRC.indexOf("}, []);", effectStart);
    const effectBody = SRC.slice(blockStart, blockEnd);

    // ++initGenRef.current must appear before fetchSettingsStatus call
    const genIncrPos = effectBody.indexOf("++initGenRef.current");
    const fetchPos = effectBody.indexOf("fetchSettingsStatus()");

    expect(genIncrPos).toBeGreaterThan(0);
    expect(fetchPos).toBeGreaterThan(genIncrPos);
  });

  it("initial effect guards setSettingsStatus with generation check", () => {
    const effectStart = SRC.indexOf("fetchSettingsStatus().then");
    const blockStart = SRC.lastIndexOf("useEffect(", effectStart);
    const blockEnd = SRC.indexOf("}, []);", effectStart);
    const effectBody = SRC.slice(blockStart, blockEnd);

    // Guard must appear before setSettingsStatus
    const guardPos = effectBody.indexOf("if (gen !== initGenRef.current) return");
    const setStatusPos = effectBody.indexOf("setSettingsStatus(");

    expect(guardPos).toBeGreaterThan(0);
    expect(setStatusPos).toBeGreaterThan(guardPos);
  });

  it("initial effect guards setRepos (from fetchRepos) with generation check", () => {
    const effectStart = SRC.indexOf("fetchSettingsStatus().then");
    const blockStart = SRC.lastIndexOf("useEffect(", effectStart);
    const blockEnd = SRC.indexOf("}, []);", effectStart);
    const effectBody = SRC.slice(blockStart, blockEnd);

    // Find the fetchRepos callback within the effect
    const fetchReposPos = effectBody.indexOf("fetchRepos().then");
    const setReposPos = effectBody.indexOf("setRepos(r)", fetchReposPos);

    // Guard must appear between fetchRepos callback start and setRepos call
    const callbackStart = effectBody.indexOf("(r) => {", fetchReposPos);
    const guardInCallback = effectBody.indexOf("if (gen !== initGenRef.current) return", callbackStart);

    expect(guardInCallback).toBeGreaterThan(callbackStart);
    expect(setReposPos).toBeGreaterThan(guardInCallback);
  });

  it("initial effect has cleanup that increments initGenRef on unmount", () => {
    const effectStart = SRC.indexOf("fetchSettingsStatus().then");
    const blockStart = SRC.lastIndexOf("useEffect(", effectStart);
    const blockEnd = SRC.indexOf("}, []);", effectStart);
    const effectBody = SRC.slice(blockStart, blockEnd);

    expect(effectBody).toContain("return () => { initGenRef.current++; };");
  });

  it("handleRepoSwitch guards fetchRepos callback with generation check", () => {
    // Find the handleRepoSwitch callback
    const switchStart = SRC.indexOf("const handleRepoSwitch = useCallback");
    const switchEnd = SRC.indexOf("}, []);", switchStart);
    const switchBody = SRC.slice(switchStart, switchEnd);

    // There must be a generation capture before fetchRepos in handleRepoSwitch
    const genCapture = switchBody.indexOf("++initGenRef.current");
    const fetchPos = switchBody.indexOf("fetchRepos().then");

    expect(genCapture).toBeGreaterThan(0);
    expect(fetchPos).toBeGreaterThan(genCapture);

    // And the callback must check the generation
    const callbackStart = switchBody.indexOf("(r) => {", fetchPos);
    const guardPos = switchBody.indexOf("initGenRef.current) return", callbackStart);

    expect(guardPos).toBeGreaterThan(callbackStart);
  });
});
