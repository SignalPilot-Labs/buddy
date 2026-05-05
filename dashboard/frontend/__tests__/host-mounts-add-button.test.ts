/**
 * Regression test: "Add Mount" button must use the shared Button component
 * with success variant and IconPlus, matching all other add buttons.
 *
 * Before the fix, it was a plain gray text button ("+ Add mount") which
 * was inconsistent with the green "Add" buttons used everywhere else.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const MOUNTS_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/HostMountsEditor.tsx"),
  "utf-8",
);

describe("HostMountsEditor: consistent add button and delete icon", () => {
  it("uses Button component for Add Mount", () => {
    expect(MOUNTS_SRC).toContain("from \"@/components/ui/Button\"");
    expect(MOUNTS_SRC).toContain("<Button");
    expect(MOUNTS_SRC).toContain('variant="success"');
  });

  it("Add Mount button has IconPlus", () => {
    expect(MOUNTS_SRC).toContain("IconPlus");
    expect(MOUNTS_SRC).toContain("from \"@/components/ui/icons\"");
  });

  it("does not use plain text '+ Add mount' button", () => {
    expect(MOUNTS_SRC).not.toContain("+ Add mount");
  });

  it("uses IconTrash for remove mount button", () => {
    expect(MOUNTS_SRC).toContain("IconTrash");
  });

  it("does not use inline X SVG for delete", () => {
    expect(MOUNTS_SRC).not.toContain('<line x1="2" y1="2" x2="8" y2="8"');
  });
});
