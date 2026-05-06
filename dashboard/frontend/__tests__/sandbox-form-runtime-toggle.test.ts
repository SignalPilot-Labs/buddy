/**
 * Regression test: switching runtime between Docker and Slurm must
 * update the start command correctly.
 *
 * Bug: switching Docker → Slurm → Docker left the Slurm command in place.
 * Fix: Docker clears the command, Slurm delegates to SlurmFieldsCard.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/settings/RemoteSandboxForm.tsx"),
  "utf-8",
);

const CARD_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/ui/SlurmFieldsCard.tsx"),
  "utf-8",
);

describe("RemoteSandboxForm: runtime toggle", () => {
  it("clears start command when switching to Docker", () => {
    const clickBlock = SRC.slice(
      SRC.indexOf("onClick={() => {", SRC.indexOf("RUNTIME_TYPES.map")),
      SRC.indexOf("className={clsx(", SRC.indexOf("RUNTIME_TYPES.map")),
    );
    expect(clickBlock).toContain('default_start_cmd: ""');
  });

  it("delegates Slurm fields to shared SlurmFieldsCard", () => {
    expect(SRC).toContain("SlurmFieldsCard");
    expect(SRC).toContain('import { SlurmFieldsCard }');
  });

  it("SlurmFieldsCard contains buildSlurmCmd", () => {
    expect(CARD_SRC).toContain("function buildSlurmCmd");
    expect(CARD_SRC).toContain("function parseSlurmCmd");
  });

  it("does not use cmdManuallyEdited state", () => {
    expect(SRC).not.toContain("cmdManuallyEdited");
  });

  it("form remounts on add vs edit via key prop", () => {
    const PARENT = fs.readFileSync(
      path.resolve(__dirname, "../components/settings/RemoteSandboxes.tsx"),
      "utf-8",
    );
    expect(PARENT).toContain('key={editingId ?? "new"}');
  });
});

describe("SandboxPicker: Slurm fields in run modal", () => {
  const PICKER_SRC = fs.readFileSync(
    path.resolve(__dirname, "../components/controls/SandboxPicker.tsx"),
    "utf-8",
  );

  it("uses SlurmFieldsCard for Slurm sandboxes", () => {
    expect(PICKER_SRC).toContain("SlurmFieldsCard");
    expect(PICKER_SRC).toContain('import { SlurmFieldsCard }');
  });

  it("shows CodeTextarea for non-Slurm remote sandboxes", () => {
    expect(PICKER_SRC).toContain("CodeTextarea");
  });
});
