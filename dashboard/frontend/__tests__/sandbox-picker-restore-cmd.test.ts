/**
 * Regression test: SandboxPicker must populate startCmd when selectedId
 * is pre-set from localStorage (no click happened).
 *
 * Before the fix, startCmd was only populated in the onClick handler.
 * When the modal opened with a sandbox restored from localStorage,
 * the start command textarea was empty until the user toggled away
 * and back. The fix adds a useEffect that runs the same fetch logic
 * when selectedId is set but startCmd is empty.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/SandboxPicker.tsx"),
  "utf-8",
);

describe("SandboxPicker: populate startCmd on localStorage restore", () => {
  it("has a useEffect that watches selectedId and sandboxes", () => {
    // Must have useEffect with [selectedId, sandboxes] deps
    expect(SRC).toContain("useEffect");
    const effectBlock = SRC.slice(
      SRC.indexOf("useEffect(() => {"),
      SRC.indexOf("return ("),
    );
    expect(effectBlock).toContain("selectedId");
    expect(effectBlock).toContain("sandboxes");
  });

  it("useEffect guards on empty startCmd (only runs when not already populated)", () => {
    const effectBlock = SRC.slice(
      SRC.indexOf("useEffect(() => {"),
      SRC.indexOf("return ("),
    );
    expect(effectBlock).toContain("!selectedId || startCmd");
  });

  it("useEffect calls fetchLastStartCmd same as onClick", () => {
    const effectBlock = SRC.slice(
      SRC.indexOf("useEffect(() => {"),
      SRC.indexOf("return ("),
    );
    expect(effectBlock).toContain("fetchLastStartCmd");
    expect(effectBlock).toContain("default_start_cmd");
  });

  it("useEffect falls back to default_start_cmd when no activeRepo", () => {
    const effectBlock = SRC.slice(
      SRC.indexOf("useEffect(() => {"),
      SRC.indexOf("return ("),
    );
    expect(effectBlock).toContain("onStartCmdChange(sandbox.default_start_cmd)");
  });

  it("onClick handler also populates startCmd (both paths exist)", () => {
    const onClickBlock = SRC.slice(
      SRC.indexOf("onClick={async"),
      SRC.indexOf("</button>\n        ))"),
    );
    expect(onClickBlock).toContain("fetchLastStartCmd");
    expect(onClickBlock).toContain("default_start_cmd");
  });
});
