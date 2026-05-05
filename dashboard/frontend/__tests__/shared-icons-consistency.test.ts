/**
 * Regression test: settings components must use shared icons from icons.tsx
 * and ListRow for consistent delete/add button styling.
 *
 * Before the fix, each section had inline SVGs with different sizes,
 * colors, and hover behaviors (some always visible, some hover-only,
 * some X icons, some text "Delete" buttons).
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SETTINGS_DIR = path.resolve(__dirname, "../components/settings");

const TOKEN_POOL = fs.readFileSync(path.join(SETTINGS_DIR, "TokenPoolSection.tsx"), "utf-8");
const REPO_LIST = fs.readFileSync(path.join(SETTINGS_DIR, "RepoListSection.tsx"), "utf-8");
const REMOTE_SANDBOXES = fs.readFileSync(path.join(SETTINGS_DIR, "RemoteSandboxes.tsx"), "utf-8");
const REMOTE_FORM = fs.readFileSync(path.join(SETTINGS_DIR, "RemoteSandboxForm.tsx"), "utf-8");

const ICONS_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/ui/icons.tsx"),
  "utf-8",
);

const LIST_ROW_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/ui/ListRow.tsx"),
  "utf-8",
);

describe("shared icons: all settings sections use icons.tsx", () => {
  it("icons.tsx exports IconPlus, IconTrash, IconPencil, IconCheck, IconX", () => {
    for (const name of ["IconPlus", "IconTrash", "IconPencil", "IconCheck", "IconX"]) {
      expect(ICONS_SRC).toContain(`export function ${name}`);
    }
  });

  it("TokenPoolSection imports from shared icons", () => {
    expect(TOKEN_POOL).toContain("from \"@/components/ui/icons\"");
    expect(TOKEN_POOL).toContain("IconPlus");
    expect(TOKEN_POOL).toContain("IconLock");
  });

  it("RepoListSection imports from shared icons", () => {
    expect(REPO_LIST).toContain("from \"@/components/ui/icons\"");
    expect(REPO_LIST).toContain("IconPlus");
    expect(REPO_LIST).toContain("IconRepo");
  });

  it("RemoteSandboxes imports from shared icons", () => {
    expect(REMOTE_SANDBOXES).toContain("from \"@/components/ui/icons\"");
    expect(REMOTE_SANDBOXES).toContain("IconPlus");
    expect(REMOTE_SANDBOXES).toContain("IconPencil");
  });

  it("RemoteSandboxForm uses IconX from shared icons", () => {
    expect(REMOTE_FORM).toContain("from \"@/components/ui/icons\"");
    expect(REMOTE_FORM).toContain("IconX");
  });
});

describe("shared ListRow: all settings list items use ListRow", () => {
  it("ListRow uses IconTrash for delete", () => {
    expect(LIST_ROW_SRC).toContain("IconTrash");
    expect(LIST_ROW_SRC).toContain("hover:text-[#ff4444]");
  });

  it("ListRow shows delete on hover only", () => {
    expect(LIST_ROW_SRC).toContain("opacity-0");
    expect(LIST_ROW_SRC).toContain("group-hover:opacity-100");
  });

  it("TokenPoolSection uses ListRow", () => {
    expect(TOKEN_POOL).toContain("ListRow");
    expect(TOKEN_POOL).toContain("from \"@/components/ui/ListRow\"");
  });

  it("RepoListSection uses ListRow", () => {
    expect(REPO_LIST).toContain("ListRow");
    expect(REPO_LIST).toContain("from \"@/components/ui/ListRow\"");
  });

  it("RemoteSandboxes uses ListRow", () => {
    expect(REMOTE_SANDBOXES).toContain("ListRow");
    expect(REMOTE_SANDBOXES).toContain("from \"@/components/ui/ListRow\"");
  });

  it("no settings component uses inline X SVG for delete (replaced by IconTrash)", () => {
    // The old pattern: inline <line x1="2" y1="2" ... for X icons used as delete
    // These should no longer appear in list item contexts
    for (const src of [TOKEN_POOL, REPO_LIST, REMOTE_SANDBOXES]) {
      // Should not have raw SVG X lines (the old delete icon pattern)
      const lineX = (src.match(/<line x1="2" y1="2" x2="8" y2="8"/g) || []).length;
      expect(lineX).toBe(0);
    }
  });
});
