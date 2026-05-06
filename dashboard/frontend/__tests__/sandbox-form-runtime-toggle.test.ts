/**
 * Regression test: switching runtime between Docker and Slurm must
 * update the start command correctly.
 *
 * Bug: switching Docker → Slurm → Docker left the Slurm command in place.
 * Fix: Docker clears the command, Slurm regenerates from fields.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/settings/RemoteSandboxForm.tsx"),
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

  it("regenerates start command when switching to Slurm", () => {
    const clickBlock = SRC.slice(
      SRC.indexOf("onClick={() => {", SRC.indexOf("RUNTIME_TYPES.map")),
      SRC.indexOf("className={clsx(", SRC.indexOf("RUNTIME_TYPES.map")),
    );
    expect(clickBlock).toContain("buildSlurmCmd(slurm)");
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
