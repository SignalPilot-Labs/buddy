/**
 * Verify frontend STARTER_PRESETS keys match the canonical
 * STARTER_PRESET_KEYS in db/constants.py.
 *
 * Prevents FE and BE preset key sets from drifting.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { STARTER_PRESET_KEYS } from "@/lib/constants";

const CONSTANTS_PY = fs.readFileSync(
  path.resolve(__dirname, "../../../db/constants.py"),
  "utf-8",
);

function extractPythonPresetKeys(): Set<string> {
  const match = CONSTANTS_PY.match(
    /STARTER_PRESET_KEYS:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(([\s\S]*?)\)/,
  );
  if (!match) throw new Error("Could not find STARTER_PRESET_KEYS in db/constants.py");
  const keys = new Set<string>();
  for (const m of match[1].matchAll(/"([^"]+)"/g)) {
    keys.add(m[1]);
  }
  return keys;
}

describe("starter preset sync", () => {
  const pyKeys = extractPythonPresetKeys();
  const tsKeys = new Set<string>(STARTER_PRESET_KEYS);

  it("Python canonical set is non-empty", () => {
    expect(pyKeys.size).toBeGreaterThan(0);
  });

  it("TypeScript set is non-empty", () => {
    expect(tsKeys.size).toBeGreaterThan(0);
  });

  it("TypeScript has all Python preset keys", () => {
    const missing = [...pyKeys].filter((k) => !tsKeys.has(k));
    expect(missing).toEqual([]);
  });

  it("Python has all TypeScript preset keys", () => {
    const extra = [...tsKeys].filter((k) => !pyKeys.has(k));
    expect(extra).toEqual([]);
  });

  it("sets are identical", () => {
    expect([...tsKeys].sort()).toEqual([...pyKeys].sort());
  });
});
