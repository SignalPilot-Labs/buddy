/**
 * CSS lint tests — prevent regressions on typography, contrast, and a11y.
 *
 * Scans all .tsx files in the frontend for patterns that violate the
 * design system. These are static source-level checks, not runtime DOM tests.
 */

import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync } from "fs";
import { join, relative } from "path";

const FRONTEND_ROOT = join(__dirname, "..");
const COMPONENTS_DIR = join(FRONTEND_ROOT, "components");
const APP_DIR = join(FRONTEND_ROOT, "app");

function collectTsxFiles(dir: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectTsxFiles(full));
    } else if (entry.name.endsWith(".tsx")) {
      results.push(full);
    }
  }
  return results;
}

function findViolations(pattern: RegExp, files: string[]): string[] {
  const hits: string[] = [];
  for (const file of files) {
    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (pattern.test(lines[i])) {
        const rel = relative(FRONTEND_ROOT, file);
        hits.push(`${rel}:${i + 1}: ${lines[i].trim()}`);
      }
    }
  }
  return hits;
}

const ALL_TSX = [...collectTsxFiles(COMPONENTS_DIR), ...collectTsxFiles(APP_DIR)];

describe("CSS lint", () => {
  it("no sub-10px font sizes (text-[7px], text-[8px], text-[9px])", () => {
    const hits = findViolations(/text-\[[789]px\]/, ALL_TSX);
    expect(hits).toEqual([]);
  });

  it("no hardcoded gray hex text colors (text-[#555] through text-[#eee])", () => {
    // Gray = all three channels identical: #555, #666, #777, #888, #999, #aaa, etc.
    // Short form: #XYZ where X=Y=Z. Long form: #XXYYZZ where XX=YY=ZZ.
    // Does NOT match chromatic colors like #ff4444, #00ff88, #88ccff.
    const shortGray = /text-\[#([0-9a-f])\1\1\]/i;
    const longGray = /text-\[#([0-9a-f]{2})\1\1\]/i;
    // Allow near-black values used as intentionally invisible dividers
    const ALLOWED = /text-\[#1a1a1a\]/;
    const hits = [
      ...findViolations(shortGray, ALL_TSX),
      ...findViolations(longGray, ALL_TSX),
    ].filter((h) => !ALLOWED.test(h));
    expect(hits).toEqual([]);
  });

  it("no bare focus: prefixes (must use focus-visible:)", () => {
    // Matches focus:border, focus:ring, focus:shadow but NOT focus-visible:
    const hits = findViolations(/(?<!-)focus:(?:border|ring|shadow)/, ALL_TSX);
    expect(hits).toEqual([]);
  });

  it("no low-contrast placeholders (placeholder-[#333] through placeholder-[#666])", () => {
    const hits = findViolations(/placeholder-?\[#[3-6][3-6][3-6]\]/, ALL_TSX);
    expect(hits).toEqual([]);
  });

  it("no redundant font-size on children that inherit from parent", () => {
    // These elements were cleaned up because they declared the same
    // text-[Npx] as their parent. If a child is inside an element that
    // already sets font-size, it should inherit — not redeclare.
    //
    // Each entry: [file, pattern that should NOT appear on the same line]
    const KNOWN_REDUNDANT: Array<[string, RegExp]> = [
      // ToolDisplayCards: DiffBlock hunk header inherits from wrapper
      ["components/feed/ToolDisplayCards.tsx", /text-\[\d+px\].*text-text-secondary.*px-3 py-1.*bg-bg-card.*font-semibold/],
      // ToolDisplayCards: gutter sign inherits from DiffBlock wrapper
      ["components/feed/ToolDisplayCards.tsx", /w-5 shrink-0 text-center select-none text-\[\d+px\]/],
      // ToolDisplayCards: "N more lines" inherits from code area parent
      ["components/feed/ToolDisplayCards.tsx", /px-2 py-1.*text-\[\d+px\].*text-text-dim text-center/],
      // ContainerLogs: empty state inherits from log content parent
      ["components/logs/ContainerLogs.tsx", /text-\[\d+px\].*text-text-dim px-2 py-6 text-center/],
    ];

    const hits: string[] = [];
    for (const [filePath, pattern] of KNOWN_REDUNDANT) {
      const full = join(FRONTEND_ROOT, filePath);
      const content = readFileSync(full, "utf-8");
      const lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (pattern.test(lines[i])) {
          hits.push(`${filePath}:${i + 1}: redundant text-[Npx] — should inherit from parent`);
        }
      }
    }
    expect(hits).toEqual([]);
  });
});
