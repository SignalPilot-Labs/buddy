/**
 * Regression test: settings page minimum font size is text-content (12px).
 * No text-caption (10px) or text-meta (11px) anywhere in settings.
 * This matches the start run modal which uses text-content as its minimum.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SETTINGS_DIR = path.resolve(__dirname, "../components/settings");
const SETTINGS_FILES = [
  "TokenPoolSection.tsx",
  "RepoListSection.tsx",
  "CredentialField.tsx",
  "RemoteSandboxes.tsx",
  "RemoteSandboxForm.tsx",
  "SecurityBanner.tsx",
];

const PAGE_SRC = fs.readFileSync(
  path.resolve(__dirname, "../app/settings/page.tsx"),
  "utf-8",
);

describe("settings: no font size smaller than text-content (12px)", () => {
  for (const file of SETTINGS_FILES) {
    it(`${file} does not use text-caption`, () => {
      const src = fs.readFileSync(path.join(SETTINGS_DIR, file), "utf-8");
      expect(src).not.toContain("text-caption");
    });

    it(`${file} does not use text-meta`, () => {
      const src = fs.readFileSync(path.join(SETTINGS_DIR, file), "utf-8");
      expect(src).not.toContain("text-meta");
    });
  }

  it("settings/page.tsx does not use text-caption or text-meta", () => {
    expect(PAGE_SRC).not.toContain("text-caption");
    expect(PAGE_SRC).not.toContain("text-meta");
  });

  it("settings components do not use text-body text-text-muted (old verbose style)", () => {
    for (const file of SETTINGS_FILES) {
      const src = fs.readFileSync(path.join(SETTINGS_DIR, file), "utf-8");
      expect(src).not.toContain("text-body text-text-muted leading-relaxed");
    }
  });
});
