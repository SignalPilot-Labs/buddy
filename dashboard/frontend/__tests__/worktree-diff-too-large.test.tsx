/**
 * Regression tests for WorkTree diffTooLarge per-source handling (BUG 14).
 *
 * Root cause: The condition `(repoOversize || tmpOversize) && !repoSafe && !tmpSafe`
 * required BOTH sources to be unusable for diffTooLarge to be set. If only the repo
 * diff was oversize (e.g., 5MB repo, 1KB tmp), diffTooLarge stayed false. Clicking
 * a repo file showed a perpetual loading spinner because the diff would never arrive.
 *
 * Fix:
 *   1. Added repoTooLarge and tmpTooLarge boolean state tracked separately.
 *   2. Changed diffTooLarge to be true when ANY source is oversize.
 *   3. Added isFileSourceTooLarge(path) helper that routes to the correct flag.
 *   4. In the "file selected but diff missing" branch, replaced the loading spinner
 *      with a "Diff too large" message when isFileSourceTooLarge returns true.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/worktree/WorkTree.tsx"),
  "utf-8",
);

describe("WorkTree: per-source diffTooLarge handling (BUG 14)", () => {
  it("declares repoTooLarge state", () => {
    expect(SRC).toContain("repoTooLarge");
    expect(SRC).toContain("setRepoTooLarge");
    expect(SRC).toContain("useState(false)");
  });

  it("declares tmpTooLarge state", () => {
    expect(SRC).toContain("tmpTooLarge");
    expect(SRC).toContain("setTmpTooLarge");
  });

  it("fetchDiffBodies sets repoTooLarge from repoOversize flag", () => {
    const fetchStart = SRC.indexOf("const fetchDiffBodies");
    expect(fetchStart).toBeGreaterThan(-1);
    const fetchEnd = SRC.indexOf("}, []);", fetchStart);
    const fetchBody = SRC.slice(fetchStart, fetchEnd + 6);

    expect(fetchBody).toContain("setRepoTooLarge(repoOversize)");
  });

  it("fetchDiffBodies sets tmpTooLarge from tmpOversize flag", () => {
    const fetchStart = SRC.indexOf("const fetchDiffBodies");
    const fetchEnd = SRC.indexOf("}, []);", fetchStart);
    const fetchBody = SRC.slice(fetchStart, fetchEnd + 6);

    expect(fetchBody).toContain("setTmpTooLarge(tmpOversize)");
  });

  it("diffTooLarge is true when ANY source is oversize (not both)", () => {
    const fetchStart = SRC.indexOf("const fetchDiffBodies");
    const fetchEnd = SRC.indexOf("}, []);", fetchStart);
    const fetchBody = SRC.slice(fetchStart, fetchEnd + 6);

    // Must use OR not AND for the any-source condition
    expect(fetchBody).toContain("setDiffTooLarge(repoOversize || tmpOversize)");
  });

  it("isFileSourceTooLarge helper is defined and routes by path prefix", () => {
    expect(SRC).toContain("isFileSourceTooLarge");
    const helperPos = SRC.indexOf("const isFileSourceTooLarge");
    expect(helperPos).toBeGreaterThan(-1);

    const helperSnippet = SRC.slice(helperPos, helperPos + 200);
    // Must route tmp/ paths to tmpTooLarge and others to repoTooLarge
    expect(helperSnippet).toContain("tmp/");
    expect(helperSnippet).toContain("tmpTooLarge");
    expect(helperSnippet).toContain("repoTooLarge");
  });

  it("JSX uses isFileSourceTooLarge to show 'too large' message instead of spinner", () => {
    // Must call the helper and conditionally render the message
    expect(SRC).toContain("isFileSourceTooLarge(selectedFile.path)");

    // The 'too large' message must be rendered in a conditional (not inside spinner)
    const tooLargePos = SRC.indexOf("Diff too large to display");
    expect(tooLargePos).toBeGreaterThan(-1);

    // The loading spinner aria-label must still exist (for the non-oversize case)
    expect(SRC).toContain("aria-label=\"Loading diff\"");

    // The 'too large' aria-label must also be present
    expect(SRC).toContain("aria-label=\"Diff too large\"");
  });

  it("run-switch effect resets repoTooLarge and tmpTooLarge", () => {
    // Find the !runId early-return block in the runId effect
    const noRunPos = SRC.indexOf("setDiffData(null)");
    expect(noRunPos).toBeGreaterThan(-1);
    const resetBlock = SRC.slice(noRunPos, noRunPos + 300);

    expect(resetBlock).toContain("setRepoTooLarge(false)");
    expect(resetBlock).toContain("setTmpTooLarge(false)");
  });

  it("new-fetch block resets repoTooLarge and tmpTooLarge before fetch", () => {
    // The gen++ block that runs for each new runId
    const genPos = SRC.indexOf("const gen = ++diffGenRef.current");
    expect(genPos).toBeGreaterThan(-1);
    const genBlock = SRC.slice(genPos, genPos + 300);

    expect(genBlock).toContain("setRepoTooLarge(false)");
    expect(genBlock).toContain("setTmpTooLarge(false)");
  });
});
