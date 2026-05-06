/**
 * Regression tests for SlurmFieldsCard textarea-to-fields desync (BUG 3).
 *
 * Root cause: The textarea and structured fields were connected only one way —
 * fields changed the textarea (via buildSlurmCmd) but editing the textarea
 * directly had no effect on the structured fields. When a user pasted a custom
 * srun command, the fields stayed stale.
 *
 * Fix: Added internalChangeRef to distinguish field-driven changes from
 * external changes. Added a useEffect watching startCmd that, when the change
 * is external, parses the new value with parseSlurmCmd and syncs the fields.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { buildSlurmCmd, parseSlurmCmd } from "@/components/ui/SlurmFieldsCard";
import type { SlurmFields } from "@/components/ui/SlurmFieldsCard";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/ui/SlurmFieldsCard.tsx"),
  "utf-8",
);

describe("SlurmFieldsCard: textarea-to-fields sync (BUG 3)", () => {
  it("internalChangeRef is declared as useRef(false)", () => {
    expect(SRC).toContain("internalChangeRef");
    expect(SRC).toContain("useRef(false)");
  });

  it("updateSlurm sets internalChangeRef.current = true before calling onStartCmdChange", () => {
    const fnStart = SRC.indexOf("const updateSlurm");
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = SRC.indexOf("\n  }, [", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 20);

    const refSetPos = fnBody.indexOf("internalChangeRef.current = true");
    const cmdCallPos = fnBody.indexOf("onStartCmdChange(cmd)");

    expect(refSetPos).toBeGreaterThan(-1);
    expect(cmdCallPos).toBeGreaterThan(-1);
    expect(refSetPos).toBeLessThan(cmdCallPos);
  });

  it("useEffect watching startCmd resets internalChangeRef and returns early for internal changes", () => {
    expect(SRC).toContain("internalChangeRef.current = false");
    // The effect must return early after resetting the ref
    const refResetIdx = SRC.indexOf("internalChangeRef.current = false");
    const returnAfterReset = SRC.slice(refResetIdx, refResetIdx + 60);
    expect(returnAfterReset).toContain("return");
  });

  it("useEffect watching startCmd calls parseSlurmCmd for external changes", () => {
    const effectIdx = SRC.indexOf("const parsed = startCmd ? parseSlurmCmd(startCmd)");
    expect(effectIdx).toBeGreaterThan(-1);
  });

  it("useEffect watching startCmd calls setSlurm(parsed) when parse succeeds", () => {
    const effectIdx = SRC.indexOf("if (parsed) setSlurm(parsed)");
    expect(effectIdx).toBeGreaterThan(-1);
  });

  it("useEffect dependency array contains startCmd", () => {
    // Find the effect block and confirm its dep array includes startCmd
    const effectStart = SRC.indexOf("if (internalChangeRef.current)");
    expect(effectStart).toBeGreaterThan(-1);
    const afterEffect = SRC.slice(effectStart);
    const depArrayIdx = afterEffect.indexOf("}, [startCmd])");
    expect(depArrayIdx).toBeGreaterThan(-1);
  });

  it("useRef and useEffect are imported from react", () => {
    const importLine = SRC.match(/import \{[^}]+\} from "react"/)?.[0] ?? "";
    expect(importLine).toContain("useEffect");
    expect(importLine).toContain("useRef");
  });
});

describe("SlurmFieldsCard: parseSlurmCmd round-trip", () => {
  it("buildSlurmCmd then parseSlurmCmd round-trips all fields", () => {
    const fields: SlurmFields = {
      partition: "gpu",
      cpus: "8",
      memory: "32G",
      gpu_gres: "a100:1",
      work_dir: "/scratch/user",
    };
    const cmd = buildSlurmCmd(fields);
    const parsed = parseSlurmCmd(cmd);

    expect(parsed).not.toBeNull();
    expect(parsed!.partition).toBe("gpu");
    expect(parsed!.cpus).toBe("8");
    expect(parsed!.memory).toBe("32G");
    expect(parsed!.gpu_gres).toBe("a100:1");
    expect(parsed!.work_dir).toBe("/scratch/user");
  });

  it("parseSlurmCmd returns null for non-slurm commands", () => {
    expect(parseSlurmCmd("docker run myimage")).toBeNull();
    expect(parseSlurmCmd("")).toBeNull();
  });

  it("buildSlurmCmd uses placeholder values for empty fields", () => {
    const cmd = buildSlurmCmd({
      partition: "",
      cpus: "",
      memory: "",
      gpu_gres: "",
      work_dir: "",
    });
    expect(cmd).toContain("PARTITION");
    expect(cmd).toContain("CPUS");
    expect(cmd).toContain("MEMORY");
    expect(cmd).toContain("WORK_DIR");
  });

  it("parseSlurmCmd strips placeholders back to empty strings", () => {
    const cmd = buildSlurmCmd({
      partition: "",
      cpus: "",
      memory: "",
      gpu_gres: "",
      work_dir: "",
    });
    const parsed = parseSlurmCmd(cmd);
    expect(parsed).not.toBeNull();
    expect(parsed!.partition).toBe("");
    expect(parsed!.cpus).toBe("");
    expect(parsed!.memory).toBe("");
    expect(parsed!.work_dir).toBe("");
  });

  it("modifying a single field and rebuilding changes only that field", () => {
    const original: SlurmFields = {
      partition: "cpu",
      cpus: "4",
      memory: "16G",
      gpu_gres: "",
      work_dir: "/home/user",
    };
    const modified: SlurmFields = { ...original, cpus: "16" };
    const cmd = buildSlurmCmd(modified);
    const parsed = parseSlurmCmd(cmd);

    expect(parsed).not.toBeNull();
    expect(parsed!.cpus).toBe("16");
    expect(parsed!.partition).toBe("cpu");
    expect(parsed!.memory).toBe("16G");
    expect(parsed!.work_dir).toBe("/home/user");
  });
});
