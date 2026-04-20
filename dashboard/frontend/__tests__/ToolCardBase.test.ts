/**
 * Regression tests for ToolCardBase — the shared tool rendering component.
 *
 * Tests buildSummary (pure logic) and source-level structural invariants
 * that guarantee card vs inline variant differences are preserved.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";
import { buildSummary } from "@/components/feed/ToolCardBase";
import { getToolCategory } from "@/lib/types";
import { makeToolCall } from "./testFactories";

/** Helper: build summary with auto-resolved category. */
function summary(tool_name: string, input_data: Record<string, unknown> | null): string {
  const tool = makeToolCall({ tool_name, input_data });
  return buildSummary(tool, getToolCategory(tool_name));
}

const SRC = readFileSync(
  join(__dirname, "..", "components", "feed", "ToolCardBase.tsx"),
  "utf-8",
);

/* ── buildSummary ── */

describe("buildSummary", () => {
  it("bash: returns command sliced to 100 chars", () => {
    const cmd = "x".repeat(200);
    expect(summary("Bash", { command: cmd })).toHaveLength(100);
  });

  it("bash: falls back to description when no command", () => {
    expect(summary("Bash", { description: "install deps" })).toBe("install deps");
  });

  it("read: returns shortened file path", () => {
    expect(summary("Read", { file_path: "/a/b/c/deep/file.ts" })).toContain("file.ts");
  });

  it("edit: returns shortened file path", () => {
    expect(summary("Edit", { file_path: "/src/index.ts" })).toContain("index.ts");
  });

  it("write: returns shortened file path", () => {
    expect(summary("Write", { file_path: "/out/bundle.js" })).toContain("bundle.js");
  });

  it("glob: returns pattern", () => {
    expect(summary("Glob", { pattern: "**/*.ts" })).toBe("**/*.ts");
  });

  it("grep: returns /pattern/ in path", () => {
    const result = summary("Grep", { pattern: "TODO", path: "/src" });
    expect(result).toContain("/TODO/");
    expect(result).toContain("src");
  });

  it("grep: returns /pattern/ without path when absent", () => {
    expect(summary("Grep", { pattern: "TODO" })).toBe("/TODO/");
  });

  it("todo: returns status counts", () => {
    const todos = [
      { status: "completed" },
      { status: "completed" },
      { status: "in_progress" },
      { status: "pending" },
      { status: "pending" },
    ];
    const result = summary("TodoWrite", { todos });
    expect(result).toContain("2✓");
    expect(result).toContain("1◉");
    expect(result).toContain("2○");
  });

  it("skill: returns skill name", () => {
    expect(summary("Skill", { skill: "commit" })).toBe("commit");
  });

  it("web_search: returns query", () => {
    expect(summary("WebSearch", { query: "vitest docs" })).toBe("vitest docs");
  });

  it("web_fetch: returns url", () => {
    expect(summary("WebFetch", { url: "https://example.com" })).toBe("https://example.com");
  });

  it("unknown tool: returns truncated JSON", () => {
    const result = summary("CustomTool", { foo: "bar" });
    expect(result).toContain("foo");
    expect(result.length).toBeLessThanOrEqual(80);
  });

  it("returns empty string for null input_data", () => {
    expect(summary("Read", null)).toBe("");
  });
});

/* ── Variant structural invariants (source-level) ── */

describe("ToolCardBase variant invariants", () => {
  it("card variant shows DENIED badge (guarded by variant === card)", () => {
    expect(SRC).toContain('variant === "card" && !tool.permitted');
  });

  it("card variant shows pending running indicator (guarded by variant === card)", () => {
    expect(SRC).toContain('variant === "card" && tool.phase === "pre"');
  });

  it("inline variant never shows DENIED or pending", () => {
    // The denied and isPending guards both require variant === "card"
    // so inline can never render them. Verify the guards exist.
    const deniedLine = SRC.split("\n").find((l) => l.includes("const denied"));
    expect(deniedLine).toContain('variant === "card"');
    const pendingLine = SRC.split("\n").find((l) => l.includes("const isPending"));
    expect(pendingLine).toContain('variant === "card"');
  });

  it("card variant renders motion.div wrapper", () => {
    expect(SRC).toContain("<motion.div");
  });

  it("inline variant renders plain div wrapper", () => {
    // The inline path returns a plain <div> (no motion.div)
    const inlinePath = SRC.slice(SRC.indexOf("if (!isCard)"), SRC.indexOf("return (", SRC.indexOf("if (!isCard)") + 1) + 200);
    expect(inlinePath).not.toContain("<motion.div");
    expect(inlinePath).toContain("<div");
  });

  it("card variant shows timestamp, inline does not", () => {
    expect(SRC).toContain("{isCard && (");
    // fmtTime is rendered inside JSX only once, inside the isCard guard
    const jsxFmtTime = SRC.split("\n").filter((l) => l.includes("fmtTime("));
    expect(jsxFmtTime).toHaveLength(1);
    const fmtTimeIdx = SRC.indexOf("fmtTime(");
    const precedingBlock = SRC.slice(Math.max(0, fmtTimeIdx - 100), fmtTimeIdx);
    expect(precedingBlock).toContain("isCard");
  });

  it("card variant has raw input details toggle", () => {
    expect(SRC).toContain("raw input");
    // Only shown for card: guarded by isCard
    const rawInputIdx = SRC.indexOf("raw input");
    const precedingBlock = SRC.slice(Math.max(0, rawInputIdx - 400), rawInputIdx);
    expect(precedingBlock).toContain("isCard");
  });
});
