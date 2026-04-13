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

  it("component font-size floors — no text below minimum per component type", () => {
    // Each component type has a minimum font size. Any text-[Npx] below
    // that floor is a violation. This catches regressions when someone
    // adds a new element at 10px in a component that should be 11px+.
    //
    // Format: [glob-relative path, minimum px, description]
    const FLOORS: Array<[string, number, string]> = [
      // Tool output content — min 11px mono
      ["components/feed/StyledToolOutput.tsx", 11, "tool output"],
      ["components/feed/ToolDisplayCards.tsx", 11, "tool display (terminal, diff, grep, file preview)"],
      // Tool call rows — min 12px for scannable content
      ["components/feed/GroupCards.tsx", 10, "group cards (10px ok for timestamps/badges)"],
      // Agent run cards — min 10px (timestamps allowed)
      ["components/feed/AgentRunCard.tsx", 10, "agent run card"],
      ["components/feed/AgentRunExpanded.tsx", 10, "agent run expanded"],
      // Message cards — min 10px (timestamps allowed)
      ["components/feed/MessageCards.tsx", 10, "message cards"],
      // Settings — min 12px for all content
      ["components/settings/CredentialField.tsx", 12, "credential field"],
      ["components/settings/RepoListSection.tsx", 12, "repo list"],
      ["components/settings/TokenPoolSection.tsx", 12, "token pool"],
      ["app/settings/page.tsx", 11, "settings page"],
      // Modals — min 12px for content
      ["components/controls/StartRunModal.tsx", 12, "start run modal"],
      ["components/onboarding/OnboardingModal.tsx", 12, "onboarding modal"],
      // Logs — min 11px mono
      ["components/logs/ContainerLogs.tsx", 11, "container logs"],
    ];

    const hits: string[] = [];
    for (const [filePath, minPx, desc] of FLOORS) {
      const full = join(FRONTEND_ROOT, filePath);
      const content = readFileSync(full, "utf-8");
      const lines = content.split("\n");
      const sizePattern = /text-\[(\d+)px\]/g;
      for (let i = 0; i < lines.length; i++) {
        let match: RegExpExecArray | null;
        sizePattern.lastIndex = 0;
        while ((match = sizePattern.exec(lines[i])) !== null) {
          const px = Number(match[1]);
          if (px < minPx) {
            hits.push(
              `${filePath}:${i + 1}: text-[${px}px] < ${minPx}px floor (${desc})`
            );
          }
        }
      }
    }
    expect(hits).toEqual([]);
  });

  it("key UI elements maintain their expected font sizes", () => {
    // Guards the design hierarchy. If someone changes a title from 14px
    // to 11px, the floor test won't catch it — but this test will.
    //
    // Format: [file, line pattern to find the element, expected size, description]
    const EXPECTED: Array<[string, RegExp, string, string]> = [
      // Feed card titles — must be 14px
      ["components/feed/ToolGroupCards.tsx", /font-medium text-\[#00ff88\]/, "text-[14px]", "BashGroupCard title"],
      ["components/feed/ToolGroupCards.tsx", /font-medium text-\[#66bbff\]/, "text-[14px]", "PlaywrightGroupCard title"],
      ["components/feed/GroupCards.tsx", /font-medium.*style=.*iconColor/, "text-[14px]", "ReadGroupCard title"],
      ["components/feed/GroupCards.tsx", /font-medium text-\[#ffcc44\]/, "text-[14px]", "EditGroupCard title"],
      ["components/feed/AgentRunCard.tsx", /className="text-\[\d+px\] font-medium"/, "text-[14px]", "AgentRunCard title"],
      ["components/feed/MessageCards.tsx", /"text-\[\d+px\] font-semibold"/, "text-[14px]", "LLM message role label"],
      // Feed body text — must be 13px
      ["components/feed/AgentRunCard.tsx", /text-text-secondary mt-0\.5 truncate/, "text-[13px]", "AgentRunCard description"],
      ["components/feed/MessageCards.tsx", /MarkdownContent.*className="text-\[\d+px\] text-\[#cce8ff\]"/, "text-[13px]", "user prompt body"],
      // Tool call rows — must be 12px
      ["components/feed/GroupCards.tsx", /w-full.*text-left.*hover:bg-white.*cursor-pointer/, "text-[12px]", "ChildToolRow"],
      ["components/feed/ToolGroupCards.tsx", /font-semibold shrink-0/, "text-[12px]", "SingleToolCard tool name"],
      // Tool output — must be 11px
      ["components/feed/StyledToolOutput.tsx", /font-mono whitespace-pre-wrap break-all/, "text-[11px]", "error output"],
      ["components/feed/StyledToolOutput.tsx", /flex items-center gap-1\.5 font-mono/, "text-[11px]", "bash command line"],
      // Modal titles — must be 14px
      ["components/controls/StartRunModal.tsx", /h2 className="text-\[\d+px\] font-semibold text-text"/, "text-[14px]", "StartRunModal title"],
      ["components/onboarding/OnboardingModal.tsx", /h2 className="text-\[\d+px\] font-semibold text-text"/, "text-[14px]", "OnboardingModal title"],
      // Settings section headers — must be 14px
      ["app/settings/page.tsx", /font-semibold text-accent-hover uppercase/, "text-[14px]", "settings section header"],
      // Sidebar — must be 13px titles, 11px meta
      ["components/sidebar/RunList.tsx", /h2 className="text-\[\d+px\] font-bold text-text-muted"/, "text-[13px]", "RunList header"],
      ["components/sidebar/RunItem.tsx", /font-medium truncate flex-1/, "text-[13px]", "RunItem title"],
    ];

    const hits: string[] = [];
    for (const [filePath, elementPattern, expectedSize, desc] of EXPECTED) {
      const full = join(FRONTEND_ROOT, filePath);
      const content = readFileSync(full, "utf-8");
      const lines = content.split("\n");
      let found = false;
      for (let i = 0; i < lines.length; i++) {
        if (elementPattern.test(lines[i])) {
          found = true;
          if (!lines[i].includes(expectedSize)) {
            hits.push(
              `${filePath}:${i + 1}: expected ${expectedSize} for ${desc}, got: ${lines[i].trim().slice(0, 80)}`
            );
          }
          break;
        }
      }
      if (!found) {
        hits.push(`${filePath}: could not find element for ${desc} (pattern: ${elementPattern})`);
      }
    }
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
