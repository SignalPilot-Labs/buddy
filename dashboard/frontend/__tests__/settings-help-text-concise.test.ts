/**
 * Regression test: settings help text must use text-caption/text-dim
 * (concise style), not text-body/text-muted (verbose paragraph style).
 *
 * Before the fix, each section had a full paragraph of explanation in
 * text-body size. Now they're single-line hints in text-caption.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SETTINGS_DIR = path.resolve(__dirname, "../components/settings");

const TOKEN_POOL = fs.readFileSync(path.join(SETTINGS_DIR, "TokenPoolSection.tsx"), "utf-8");
const REPO_LIST = fs.readFileSync(path.join(SETTINGS_DIR, "RepoListSection.tsx"), "utf-8");
const CREDENTIAL = fs.readFileSync(path.join(SETTINGS_DIR, "CredentialField.tsx"), "utf-8");

describe("settings: help text uses concise caption style", () => {
  it("TokenPoolSection help text uses text-caption not text-body", () => {
    // Should have caption-sized help text
    expect(TOKEN_POOL).toContain("text-caption text-text-dim");
    // Should not have old verbose style
    expect(TOKEN_POOL).not.toContain("text-body text-text-muted leading-relaxed");
  });

  it("RepoListSection does not have verbose help paragraph", () => {
    // The old pattern had a full paragraph below the add input
    expect(REPO_LIST).not.toContain("text-body text-text-muted leading-relaxed");
  });

  it("CredentialField help text uses text-caption not text-body", () => {
    expect(CREDENTIAL).toContain("text-caption text-text-dim");
    expect(CREDENTIAL).not.toContain("text-body text-text-muted");
  });
});
