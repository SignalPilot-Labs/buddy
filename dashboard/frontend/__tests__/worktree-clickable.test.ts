/**
 * WorkTree file clickability regression test.
 *
 * Verifies that onFileClick is not gated on diff body availability,
 * preventing the bug where files appear in the tree but aren't clickable
 * until diff bodies finish loading (or until switching tabs and back).
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const WORKTREE_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/worktree/WorkTree.tsx"),
  "utf-8",
);

describe("WorkTree: file clickability", () => {
  it("onFileClick is gated on hasContent, not on diff body availability", () => {
    // The old bug: onFileClick was `(repoDiff !== null || tmpDiff !== null) ? handler : null`
    // which made files unclickable until async diff bodies loaded.
    // Now it should be gated on `hasContent` (tree has nodes to show).
    const onFileClickLine = WORKTREE_SRC.split("\n").find((l) =>
      l.includes("const onFileClick") && l.includes("hasContent"),
    );
    expect(onFileClickLine).toBeDefined();
  });

  it("onFileClick does NOT depend on repoDiff or tmpDiff", () => {
    // Extract the onFileClick assignment line(s)
    const lines = WORKTREE_SRC.split("\n");
    const onFileClickIdx = lines.findIndex((l) => l.includes("const onFileClick"));
    // Check the assignment line and the next few lines (in case it spans multiple)
    const assignmentBlock = lines.slice(onFileClickIdx, onFileClickIdx + 4).join("\n");
    expect(assignmentBlock).not.toContain("repoDiff !== null");
    expect(assignmentBlock).not.toContain("tmpDiff !== null");
  });

  it("shows a loading state when file is selected but diff body is not ready", () => {
    // There should be a branch for `selectedFile !== null` that shows a spinner
    // when diffForPath returns null (body still loading)
    expect(WORKTREE_SRC).toContain('aria-label="Loading diff"');
  });

  it("loading state has a back button to return to tree", () => {
    // The loading state between selectedFile and diff body should have a back button
    const loadingDiffIdx = WORKTREE_SRC.indexOf('aria-label="Loading diff"');
    const precedingBlock = WORKTREE_SRC.slice(Math.max(0, loadingDiffIdx - 600), loadingDiffIdx);
    expect(precedingBlock).toContain("setSelectedFile(null)");
    expect(precedingBlock).toContain("Back");
  });
});
