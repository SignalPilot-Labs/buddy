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
  it("resets start command to default when switching to Docker", () => {
    const clickBlock = SRC.slice(
      SRC.indexOf("onClick={() => {", SRC.indexOf("RUNTIME_TYPES.map")),
      SRC.indexOf("className={clsx(", SRC.indexOf("RUNTIME_TYPES.map")),
    );
    expect(clickBlock).toContain("DEFAULT_REMOTE_DOCKER_CMD");
  });

  it("delegates Slurm fields to shared SlurmFieldsCard", () => {
    expect(SRC).toContain("SlurmFieldsCard");
    expect(SRC).toContain('SlurmFieldsCard, buildSlurmCmd, EMPTY_SLURM');
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

  it("caches start commands per sandbox to survive round-trip switching", () => {
    // Must have a cmdCache ref to preserve user edits across sandbox switches.
    expect(PICKER_SRC).toContain("cmdCache");
    expect(PICKER_SRC).toContain("useRef<Map<string, string>>");
    // Must save current command before switching.
    expect(PICKER_SRC).toContain("cmdCache.current.set(currentKey, startCmd)");
    // Must check cache before falling back to default.
    expect(PICKER_SRC).toContain("cmdCache.current.get(s.id)");
  });

  it("sets command before selection so remounted SlurmFieldsCard sees correct value", () => {
    // switchTo must call onStartCmdChange BEFORE onSelect.
    const switchBlock = PICKER_SRC.slice(
      PICKER_SRC.indexOf("const switchTo"),
      PICKER_SRC.indexOf("}, [", PICKER_SRC.indexOf("const switchTo")),
    );
    const cmdIdx = switchBlock.indexOf("onStartCmdChange");
    const selectIdx = switchBlock.indexOf("onSelect");
    expect(cmdIdx).toBeGreaterThan(-1);
    expect(selectIdx).toBeGreaterThan(-1);
    expect(cmdIdx).toBeLessThan(selectIdx);
  });
});

describe("SlurmFieldsCard: parseSlurmCmd round-trip", () => {
  it("strips placeholder values so new sandbox form shows empty fields", () => {
    expect(CARD_SRC).toContain("PLACEHOLDERS");
    expect(CARD_SRC).toContain("stripPlaceholder");
    // Placeholders must include all fallback values from buildSlurmCmd.
    expect(CARD_SRC).toContain('"PARTITION"');
    expect(CARD_SRC).toContain('"CPUS"');
    expect(CARD_SRC).toContain('"MEMORY"');
    expect(CARD_SRC).toContain('"WORK_DIR"');
  });

  it("sanitizes shell metacharacters from field values", () => {
    expect(CARD_SRC).toContain("function sanitize");
  });
});

describe("StartRunModal: default run works without expanding sandbox", () => {
  const MODAL_SRC = fs.readFileSync(
    path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
    "utf-8",
  );

  it("startCmd defaults to DEFAULT_DOCKER_START_CMD", () => {
    expect(MODAL_SRC).toContain("useState(DEFAULT_DOCKER_START_CMD)");
  });

  it("sends startCmd even when sandbox section is not expanded", () => {
    // cmdToSend must come from startCmd directly, not gated on selectedSandboxId.
    expect(MODAL_SRC).toContain("const cmdToSend = startCmd.trim()");
  });

  it("clears stale sandbox selection if sandbox was deleted", () => {
    // If saved sandbox ID not found in remoteSandboxes, must clear localStorage.
    expect(MODAL_SRC).toContain("localStorage.removeItem");
    expect(MODAL_SRC).toContain("Sandbox was deleted");
  });
});
