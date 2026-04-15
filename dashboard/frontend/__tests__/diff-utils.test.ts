/**
 * Tests for diff parsing utilities.
 *
 * Covers parseDiffLines (hunk headers, add/remove/context lines,
 * line numbering) and langFromPath (extension → language mapping).
 */

import { describe, it, expect } from "vitest";
import { parseDiffLines, langFromPath, extractFilePatch } from "@/lib/diff-utils";

describe("parseDiffLines", () => {
  it("parses hunk header and extracts line numbers", () => {
    const lines = parseDiffLines("@@ -10,3 +20,4 @@ function foo() {");
    expect(lines[0].type).toBe("hunk-header");
    expect(lines[0].content).toContain("@@ -10,3 +20,4 @@");
  });

  it("parses added lines with correct line numbers", () => {
    const patch = "@@ -1,2 +1,3 @@\n context\n+added\n context2";
    const lines = parseDiffLines(patch);
    const added = lines.find(l => l.type === "add");
    expect(added).toBeDefined();
    expect(added!.content).toBe("added");
    expect(added!.oldLine).toBeNull();
    expect(added!.newLine).toBe(2);
  });

  it("parses removed lines with correct line numbers", () => {
    const patch = "@@ -1,3 +1,2 @@\n context\n-removed\n context2";
    const lines = parseDiffLines(patch);
    const removed = lines.find(l => l.type === "remove");
    expect(removed).toBeDefined();
    expect(removed!.content).toBe("removed");
    expect(removed!.oldLine).toBe(2);
    expect(removed!.newLine).toBeNull();
  });

  it("parses context lines with both line numbers", () => {
    const patch = "@@ -5,2 +10,2 @@\n context line\n another";
    const lines = parseDiffLines(patch);
    const ctx = lines.find(l => l.type === "context");
    expect(ctx).toBeDefined();
    expect(ctx!.oldLine).toBe(5);
    expect(ctx!.newLine).toBe(10);
  });

  it("identifies meta lines", () => {
    const patch = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new";
    const lines = parseDiffLines(patch);
    const meta = lines.filter(l => l.type === "meta");
    expect(meta.length).toBe(2);
    expect(meta[0].content).toBe("--- a/foo.py");
  });

  it("handles empty patch", () => {
    const lines = parseDiffLines("");
    expect(lines.length).toBe(1);
    expect(lines[0].type).toBe("context");
  });

  it("increments line numbers across multiple hunks", () => {
    const patch = "@@ -1,2 +1,2 @@\n-old\n+new\n@@ -10,1 +10,1 @@\n-old2\n+new2";
    const lines = parseDiffLines(patch);
    const secondAdd = lines.filter(l => l.type === "add")[1];
    expect(secondAdd.newLine).toBe(10);
  });
});

describe("langFromPath", () => {
  it("maps .py to python", () => {
    expect(langFromPath("src/main.py")).toBe("python");
  });

  it("maps .ts to typescript", () => {
    expect(langFromPath("lib/utils.ts")).toBe("typescript");
  });

  it("maps .tsx to typescript", () => {
    expect(langFromPath("components/App.tsx")).toBe("typescript");
  });

  it("maps .yml to yaml", () => {
    expect(langFromPath("config.yml")).toBe("yaml");
  });

  it("returns text for unknown extensions", () => {
    expect(langFromPath("README.txt")).toBe("text");
  });

  it("returns text for no extension", () => {
    expect(langFromPath("Makefile")).toBe("text");
  });
});

const SAMPLE_DIFF = `diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,2 +1,3 @@
 import os
+import sys
diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -1 +1,2 @@
 def helper():
+    pass
`;

describe("extractFilePatch", () => {
  it("extracts patch for a file", () => {
    const patch = extractFilePatch(SAMPLE_DIFF, "src/main.py");
    expect(patch).not.toBeNull();
    expect(patch).toContain("+import sys");
    expect(patch).not.toContain("helper");
  });

  it("returns null for missing file", () => {
    expect(extractFilePatch(SAMPLE_DIFF, "nope.py")).toBeNull();
  });

  it("no prefix false positive", () => {
    const diff = `diff --git a/foo.py.bak b/foo.py.bak
+++ b/foo.py.bak
@@ -1 +1,2 @@
+new
`;
    expect(extractFilePatch(diff, "foo.py")).toBeNull();
  });

  it("returns null for binary files", () => {
    const diff = `diff --git a/img.png b/img.png
Binary files a/img.png and b/img.png differ
`;
    expect(extractFilePatch(diff, "img.png")).toBeNull();
  });

  it("handles empty diff", () => {
    expect(extractFilePatch("", "any.py")).toBeNull();
  });
});
