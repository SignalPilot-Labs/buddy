/**
 * Regression tests for StartRunModal mounts loaded for wrong sandbox (BUG 4).
 *
 * Root cause: The general data-loading effect (deps: [open, activeRepo, loadMountsForSandbox])
 * called loadMountsForSandbox(selectedSandboxId). This fired on modal open with
 * selectedSandboxId from the previous render cycle (before the reset effect cleared
 * it to null). Then the restoration effect fired asynchronously (after remoteSandboxes
 * loaded) and set selectedSandboxId to the saved sandbox — but the mounts effect
 * did NOT re-fire because selectedSandboxId was not in its dependency array.
 *
 * Fix:
 * 1. Remove loadMountsForSandbox(selectedSandboxId) from the general data-loading effect.
 * 2. In the reset-on-open effect, call void loadMountsForSandbox(null) when activeRepo
 *    is set — this loads local-Docker mounts immediately on open.
 * 3. In the restoration effect, call void loadMountsForSandbox(saved) after
 *    setSelectedSandboxId(saved) — this overwrites with remote mounts when a
 *    saved sandbox is restored.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
  "utf-8",
);

describe("StartRunModal: mounts loaded for correct sandbox on open (BUG 4)", () => {
  it("general data-loading effect does NOT call loadMountsForSandbox", () => {
    // Find the effect that loads env and MCP (deps: [open, activeRepo])
    const envFetchIdx = SRC.indexOf("fetchRepoEnv(activeRepo)");
    expect(envFetchIdx).toBeGreaterThan(-1);

    // Locate the effect containing this call
    const effectStart = SRC.lastIndexOf("useEffect(() => {", envFetchIdx);
    const effectEnd = SRC.indexOf("}, [open, activeRepo]);", effectStart);
    expect(effectEnd).toBeGreaterThan(effectStart);

    const effectBody = SRC.slice(effectStart, effectEnd);
    // This effect must NOT call loadMountsForSandbox
    expect(effectBody).not.toContain("loadMountsForSandbox");
  });

  it("reset-on-open effect calls loadMountsForSandbox(null) when activeRepo is set", () => {
    // Find the reset-on-open effect (identified by prevOpenRef and !wasOpen && open)
    const resetEffectIdx = SRC.indexOf("!wasOpen && open");
    expect(resetEffectIdx).toBeGreaterThan(-1);

    const effectStart = SRC.lastIndexOf("useEffect(() => {", resetEffectIdx);
    const effectEnd = SRC.indexOf("}, [open, activeRepo, loadMountsForSandbox]);", effectStart);
    expect(effectEnd).toBeGreaterThan(effectStart);

    const effectBody = SRC.slice(effectStart, effectEnd);
    expect(effectBody).toContain("loadMountsForSandbox(null)");
    expect(effectBody).toContain("if (activeRepo)");
  });

  it("reset-on-open effect has loadMountsForSandbox in its dependency array", () => {
    const resetEffectIdx = SRC.indexOf("!wasOpen && open");
    const effectStart = SRC.lastIndexOf("useEffect(() => {", resetEffectIdx);
    // Must end with the deps array that includes loadMountsForSandbox
    const depsLine = SRC.slice(effectStart).indexOf("}, [open, activeRepo, loadMountsForSandbox]);");
    expect(depsLine).toBeGreaterThan(-1);
  });

  it("restoration effect calls loadMountsForSandbox(saved) after setSelectedSandboxId(saved)", () => {
    // Find the restoration effect (identified by autofyn_last_sandbox localStorage key)
    const restorationIdx = SRC.indexOf("autofyn_last_sandbox:");
    expect(restorationIdx).toBeGreaterThan(-1);

    const effectStart = SRC.lastIndexOf("useEffect(() => {", restorationIdx);
    const effectEnd = SRC.indexOf("}, [open, activeRepo, remoteSandboxes, loadMountsForSandbox]);", effectStart);
    expect(effectEnd).toBeGreaterThan(effectStart);

    const effectBody = SRC.slice(effectStart, effectEnd);

    // Must call loadMountsForSandbox with the saved sandbox id
    expect(effectBody).toContain("loadMountsForSandbox(saved)");

    // setSelectedSandboxId must come before loadMountsForSandbox
    const setIdPos = effectBody.indexOf("setSelectedSandboxId(saved)");
    const loadMountsPos = effectBody.indexOf("loadMountsForSandbox(saved)");
    expect(setIdPos).toBeGreaterThan(0);
    expect(loadMountsPos).toBeGreaterThan(setIdPos);
  });

  it("restoration effect has loadMountsForSandbox in its dependency array", () => {
    const restorationIdx = SRC.indexOf("autofyn_last_sandbox:");
    const effectStart = SRC.lastIndexOf("useEffect(() => {", restorationIdx);
    const depsLine = SRC.slice(effectStart).indexOf("}, [open, activeRepo, remoteSandboxes, loadMountsForSandbox]);");
    expect(depsLine).toBeGreaterThan(-1);
  });

  it("loadMountsForSandbox is declared before the reset-on-open effect that uses it", () => {
    const loadMountsDecl = SRC.indexOf("const loadMountsForSandbox = useCallback");
    const resetEffectIdx = SRC.indexOf("!wasOpen && open");
    const resetEffectStart = SRC.lastIndexOf("useEffect(() => {", resetEffectIdx);

    expect(loadMountsDecl).toBeGreaterThan(0);
    expect(resetEffectStart).toBeGreaterThan(loadMountsDecl);
  });

  it("handleSandboxSelect still calls loadMountsForSandbox for user-initiated changes", () => {
    const fnStart = SRC.indexOf("const handleSandboxSelect");
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = SRC.indexOf("}, [loadMountsForSandbox, activeRepo]);", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd);

    expect(fnBody).toContain("loadMountsForSandbox(id)");
  });
});
