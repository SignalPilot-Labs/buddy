/**
 * Regression tests for MobileControlSheet simplification (PR #236).
 *
 * Ensures removed props stay removed and run controls only render for active runs.
 */

import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

const SHEET_PATH = path.resolve(
  __dirname,
  "../components/mobile/MobileControlSheet.tsx",
);
const REPO_SELECTOR_PATH = path.resolve(
  __dirname,
  "../components/ui/RepoSelector.tsx",
);

const sheetSrc = fs.readFileSync(SHEET_PATH, "utf-8");
const repoSrc = fs.readFileSync(REPO_SELECTOR_PATH, "utf-8");

describe("MobileControlSheet", () => {
  it("does not accept onPause prop", () => {
    expect(sheetSrc).not.toMatch(/onPause/);
  });

  it("does not accept onResume prop", () => {
    expect(sheetSrc).not.toMatch(/onResume/);
  });

  it("does not accept onToggleInject prop", () => {
    expect(sheetSrc).not.toMatch(/onToggleInject/);
  });

  it("only shows run controls when status is active", () => {
    // The guard must check both status and isActive
    expect(sheetSrc).toMatch(/status\s*&&\s*isActive/);
  });
});

describe("RepoSelector dropdownMaxHeight", () => {
  it("is a required prop (no optional marker)", () => {
    // Match the interface line — must NOT have `?:` for dropdownMaxHeight
    const interfaceMatch = repoSrc.match(/dropdownMaxHeight\s*(\??)\s*:/);
    expect(interfaceMatch).not.toBeNull();
    expect(interfaceMatch![1]).toBe("");
  });

  it("does not use a fallback default for dropdownMaxHeight", () => {
    // No `??` fallback for the prop value
    expect(repoSrc).not.toMatch(/dropdownMaxHeight\s*\?\?/);
  });
});
