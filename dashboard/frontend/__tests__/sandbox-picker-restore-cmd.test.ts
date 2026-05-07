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
 * restores selectedSandboxId from localStorage using sandbox.default_start_cmd.
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
    const restoreStart = MODAL_SRC.indexOf("Restore last-used sandbox");
    const restoreEnd = MODAL_SRC.indexOf("adjustPromptHeight", restoreStart);
    const restoreBlock = MODAL_SRC.slice(restoreStart, restoreEnd);
    expect(restoreBlock).toContain("localStorage.getItem");
    expect(restoreBlock).toContain("setSelectedSandboxId");
    expect(restoreBlock).toContain("setStartCmd");
    expect(restoreBlock).toContain("default_start_cmd");
  });

  it("SandboxPicker does NOT have a useEffect for startCmd population", () => {
    expect(PICKER_SRC).not.toContain("useEffect");
  });

  it("SandboxPicker populates startCmd on manual selection via handleRemoteClick", () => {
    expect(PICKER_SRC).toContain("handleRemoteClick");
    expect(PICKER_SRC).toContain("default_start_cmd");
  });
});
