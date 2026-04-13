/**
 * CSS lint tests — prevent regressions on typography, contrast, and a11y.
 *
 * Scans all .tsx files in the frontend for patterns that violate the
 * design system. These are static source-level checks, not runtime DOM tests.
 *
 * Typography tokens (defined in globals.css @theme):
 *   text-title   = 14px  (card titles, section headers, modal titles)
 *   text-body    = 13px  (message body, help paragraphs, section labels)
 *   text-content = 12px  (tool names, list items, inputs, buttons, descriptions)
 *   text-meta    = 11px  (timestamps, durations, costs, tab labels)
 *   text-caption = 10px  (tiny badges, diff stats, status letters)
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
  it("no raw text-[Npx] — must use design tokens (text-title/body/content/meta/caption)", () => {
    // Only text-[15px] and text-[18px] are allowed (MarkdownContent heading hierarchy).
    // Everything else must use a token: text-title, text-body, text-content, text-meta, text-caption.
    const RAW_SIZE = /text-\[(\d+)px\]/;
    const ALLOWED_SIZES = new Set([15, 18]);
    const hits: string[] = [];
    for (const file of ALL_TSX) {
      const content = readFileSync(file, "utf-8");
      const lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        const match = RAW_SIZE.exec(lines[i]);
        if (match && !ALLOWED_SIZES.has(Number(match[1]))) {
          const rel = relative(FRONTEND_ROOT, file);
          hits.push(`${rel}:${i + 1}: raw text-[${match[1]}px] — use a token instead`);
        }
      }
    }
    expect(hits).toEqual([]);
  });

  it("no hardcoded gray hex text colors (text-[#555] through text-[#eee])", () => {
    const shortGray = /text-\[#([0-9a-f])\1\1\]/i;
    const longGray = /text-\[#([0-9a-f]{2})\1\1\]/i;
    const ALLOWED = /text-\[#1a1a1a\]/;
    const hits = [
      ...findViolations(shortGray, ALL_TSX),
      ...findViolations(longGray, ALL_TSX),
    ].filter((h) => !ALLOWED.test(h));
    expect(hits).toEqual([]);
  });

  it("no bare focus: prefixes (must use focus-visible:)", () => {
    const hits = findViolations(/(?<!-)focus:(?:border|ring|shadow)/, ALL_TSX);
    expect(hits).toEqual([]);
  });

  it("no low-contrast placeholders (placeholder-[#333] through placeholder-[#666])", () => {
    const hits = findViolations(/placeholder-?\[#[3-6][3-6][3-6]\]/, ALL_TSX);
    expect(hits).toEqual([]);
  });

  it("key UI elements use correct tokens", () => {
    // Guards the design hierarchy. Pins critical elements to their token.
    // Format: [file, pattern to find the element, expected token, description]
    const EXPECTED: Array<[string, RegExp, string, string]> = [
      // Feed card titles — must be text-title
      ["components/feed/ToolGroupCards.tsx", /font-medium text-\[#00ff88\]/, "text-title", "BashGroupCard title"],
      ["components/feed/ToolGroupCards.tsx", /font-medium text-\[#66bbff\]/, "text-title", "PlaywrightGroupCard title"],
      ["components/feed/GroupCards.tsx", /font-medium.*style=.*iconColor/, "text-title", "ReadGroupCard title"],
      ["components/feed/GroupCards.tsx", /font-medium text-\[#ffcc44\]/, "text-title", "EditGroupCard title"],
      ["components/feed/AgentRunCard.tsx", /className="text-\w+ font-medium"$/, "text-title", "AgentRunCard title"],
      // Feed body text — must be text-body
      ["components/feed/AgentRunCard.tsx", /text-text-secondary mt-0\.5 truncate/, "text-body", "AgentRunCard description"],
      // Tool call rows — must be text-content
      ["components/feed/GroupCards.tsx", /w-full.*text-left.*hover:bg-white.*cursor-pointer/, "text-content", "ChildToolRow"],
      ["components/feed/ToolGroupCards.tsx", /font-semibold shrink-0/, "text-content", "SingleToolCard tool name"],
      // Tool output — must be text-meta
      ["components/feed/StyledToolOutput.tsx", /font-mono whitespace-pre-wrap break-all/, "text-meta", "error output"],
      ["components/feed/StyledToolOutput.tsx", /flex items-center gap-1\.5 font-mono/, "text-meta", "bash command line"],
      // Modal titles — must be text-title
      ["components/controls/StartRunModal.tsx", /h2 className="text-\w+ font-semibold text-text"/, "text-title", "StartRunModal title"],
      ["components/onboarding/OnboardingModal.tsx", /h2 className="text-\w+ font-semibold text-text"/, "text-title", "OnboardingModal title"],
      // Settings section headers — must be text-title
      ["app/settings/page.tsx", /font-semibold text-accent-hover uppercase/, "text-title", "settings section header"],
      // Sidebar
      ["components/sidebar/RunList.tsx", /h2 className="text-\w+ font-bold text-text-muted"/, "text-body", "RunList header"],
      ["components/sidebar/RunItem.tsx", /font-medium truncate flex-1/, "text-body", "RunItem title"],
      // Expanded agent sections — prompt/summary content must be text-content
      ["components/feed/AgentRunExpanded.tsx", /text-accent-hover whitespace-pre-wrap/, "text-content", "Prompt content"],
      ["components/feed/AgentRunExpanded.tsx", /className="text-\w+ text-accent-hover"/, "text-content", "Agent Summary content"],
      ["components/feed/AgentRunExpanded.tsx", /className="text-\w+ text-text-secondary"/, "text-content", "Result content"],
    ];

    const hits: string[] = [];
    for (const [filePath, elementPattern, expectedToken, desc] of EXPECTED) {
      const full = join(FRONTEND_ROOT, filePath);
      const content = readFileSync(full, "utf-8");
      const lines = content.split("\n");
      let found = false;
      for (let i = 0; i < lines.length; i++) {
        if (elementPattern.test(lines[i])) {
          found = true;
          if (!lines[i].includes(expectedToken)) {
            hits.push(
              `${filePath}:${i + 1}: expected ${expectedToken} for ${desc}, got: ${lines[i].trim().slice(0, 80)}`
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
});
