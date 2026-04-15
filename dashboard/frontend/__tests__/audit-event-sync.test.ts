/**
 * Verify frontend AuditEventType matches the canonical AUDIT_EVENT_TYPES
 * in db/constants.py.
 *
 * This test reads the Python source directly and extracts the set of
 * event types, then compares it against the TypeScript union.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const CONSTANTS_PY = fs.readFileSync(
  path.resolve(__dirname, "../../../db/constants.py"),
  "utf-8",
);

const TYPES_TS = fs.readFileSync(
  path.resolve(__dirname, "../lib/types.ts"),
  "utf-8",
);

function extractPythonAuditTypes(): Set<string> {
  // Extract the AUDIT_EVENT_TYPES frozenset block
  const match = CONSTANTS_PY.match(
    /AUDIT_EVENT_TYPES:\s*frozenset\[str\]\s*=\s*frozenset\(\{([\s\S]*?)\}\)/,
  );
  if (!match) throw new Error("Could not find AUDIT_EVENT_TYPES in db/constants.py");
  const types = new Set<string>();
  for (const m of match[1].matchAll(/"([^"]+)"/g)) {
    types.add(m[1]);
  }
  return types;
}

function extractTypeScriptAuditTypes(): Set<string> {
  // Extract the AuditEventType union members
  const match = TYPES_TS.match(
    /export type AuditEventType\s*=([\s\S]*?);/,
  );
  if (!match) throw new Error("Could not find AuditEventType in types.ts");
  const types = new Set<string>();
  for (const m of match[1].matchAll(/"([^"]+)"/g)) {
    types.add(m[1]);
  }
  return types;
}

describe("audit event type sync", () => {
  const pyTypes = extractPythonAuditTypes();
  const tsTypes = extractTypeScriptAuditTypes();

  it("Python canonical set is non-empty", () => {
    expect(pyTypes.size).toBeGreaterThan(20);
  });

  it("TypeScript type is non-empty", () => {
    expect(tsTypes.size).toBeGreaterThan(20);
  });

  it("TypeScript has all Python types", () => {
    const missing = [...pyTypes].filter((t) => !tsTypes.has(t));
    expect(missing).toEqual([]);
  });

  it("Python has all TypeScript types", () => {
    const extra = [...tsTypes].filter((t) => !pyTypes.has(t));
    expect(extra).toEqual([]);
  });

  it("sets are identical", () => {
    expect([...tsTypes].sort()).toEqual([...pyTypes].sort());
  });
});
