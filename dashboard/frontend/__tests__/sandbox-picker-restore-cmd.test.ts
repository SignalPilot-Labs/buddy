/**
 * Regression test: StartRunModal must populate startCmd when selectedSandboxId
 * is restored from localStorage — even if the Sandbox collapsible section
 * is never expanded.
 *
 * Root cause: startCmd population was inside SandboxPicker's useEffect, but
 * SandboxPicker only mounts when CollapsibleSection is open. If the user
 * never expands it, startCmd stays empty and the run fails with
 * "start command required".
 *
 * Fix: StartRunModal itself populates startCmd in the same useEffect that
 * restores selectedSandboxId from localStorage.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const MODAL_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
  "utf-8",
);

const PICKER_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/SandboxPicker.tsx"),
  "utf-8",
);

describe("StartRunModal: populate startCmd on localStorage restore", () => {
  it("modal restores startCmd in the same effect that restores selectedSandboxId", () => {
    // The effect that reads localStorage must also call fetchLastStartCmd
    const restoreBlock = MODAL_SRC.slice(
      MODAL_SRC.indexOf("Restore last-used sandbox"),
      MODAL_SRC.indexOf("const adjustPromptHeight"),
    );
    expect(restoreBlock).toContain("localStorage.getItem");
    expect(restoreBlock).toContain("setSelectedSandboxId");
    expect(restoreBlock).toContain("fetchLastStartCmd");
    expect(restoreBlock).toContain("setStartCmd");
  });

  it("modal imports fetchLastStartCmd", () => {
    expect(MODAL_SRC).toContain("fetchLastStartCmd");
  });

  it("SandboxPicker does NOT have a useEffect for startCmd population", () => {
    // The logic lives in the modal now, not in the picker
    expect(PICKER_SRC).not.toContain("useEffect");
  });

  it("SandboxPicker onClick still populates startCmd on manual selection", () => {
    const start = PICKER_SRC.indexOf("onClick={async");
    const end = PICKER_SRC.indexOf("}}", start) + 2;
    const onClickBlock = PICKER_SRC.slice(start, end);
    expect(onClickBlock).toContain("fetchLastStartCmd");
    expect(onClickBlock).toContain("default_start_cmd");
  });
});
