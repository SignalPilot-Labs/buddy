/**
 * Regression test: health poll check() must have try/catch around
 * fetchAgentHealth() so network errors are caught and agentHealth is
 * set to null (disconnected state) rather than leaving state stale.
 *
 * Before the fix, check() had no try/catch — any error that escaped
 * fetchAgentHealth() (e.g., a response parse failure after a non-ok
 * response) became an unhandled promise rejection, silently stopping
 * health updates and leaving the UI with stale data.
 *
 * The fix wraps the await fetchAgentHealth() call in try/catch and
 * calls setAgentHealth(null) on error.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useDashboard.ts"),
  "utf-8",
);

// Extract the health poll useEffect block
function getHealthPollBlock(): string {
  const startMarker = "// Health poll:";
  const startIdx = SRC.indexOf(startMarker);
  if (startIdx === -1) throw new Error("Health poll comment not found in useDashboard.ts");
  // The health poll effect closes with }, [])
  const endIdx = SRC.indexOf("}, [])", startIdx) + 10;
  return SRC.slice(startIdx, endIdx);
}

describe("health poll: error handling (Bug 2)", () => {
  it("check() wraps fetchAgentHealth in try/catch", () => {
    const block = getHealthPollBlock();
    expect(block).toContain("try {");
    expect(block).toContain("catch");
  });

  it("catch block calls setAgentHealth(null) on error", () => {
    const block = getHealthPollBlock();
    expect(block).toContain("setAgentHealth(null)");
  });

  it("catch block logs the error to console", () => {
    const block = getHealthPollBlock();
    // Must log the error — either console.error or console.warn
    const hasLog = block.includes("console.error") || block.includes("console.warn");
    expect(hasLog).toBe(true);
  });

  it("fetchAgentHealth call is inside the try block", () => {
    const block = getHealthPollBlock();
    const tryIdx = block.indexOf("try {");
    const fetchIdx = block.indexOf("fetchAgentHealth()");
    const catchIdx = block.indexOf("} catch");
    expect(tryIdx).toBeGreaterThan(-1);
    expect(fetchIdx).toBeGreaterThan(tryIdx);
    expect(fetchIdx).toBeLessThan(catchIdx);
  });

  it("setAgentHealth state update is inside the try block (not lost on error)", () => {
    const block = getHealthPollBlock();
    const tryIdx = block.indexOf("try {");
    // The state updater with prevIds/hasNewRun logic lives inside try
    const stateUpdateIdx = block.indexOf("setAgentHealth((prev)");
    const catchIdx = block.indexOf("} catch");
    expect(stateUpdateIdx).toBeGreaterThan(tryIdx);
    expect(stateUpdateIdx).toBeLessThan(catchIdx);
  });
});
