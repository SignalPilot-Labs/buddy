/**
 * Regression test: keyboard shortcut 'n' must not open the modal without an active repo,
 * and handleStart must fail fast if env vars or mounts are set without an active repo.
 *
 * Before the fix:
 * 1. useKeyboardShortcuts opened the modal on 'n' without checking activeRepoFilter,
 *    unlike page.tsx:180 which has an explicit guard.
 * 2. handleStart in StartRunModal silently discarded env vars and mounts when
 *    activeRepo was null — the if (activeRepo) block simply skipped saving them.
 *
 * The fix:
 * Part A — useKeyboardShortcuts: added activeRepoFilter to the options interface;
 *   the 'n' handler returns early if !activeRepoFilter.
 * Part C — StartRunModal.handleStart: added a fail-fast check that errors out
 *   if !activeRepo and the user has entered env vars or mounts.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SHORTCUTS_SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useKeyboardShortcuts.ts"),
  "utf-8",
);

const MODAL_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
  "utf-8",
);

describe("useKeyboardShortcuts: 'n' key must check activeRepoFilter", () => {
  it("UseKeyboardShortcutsOptions includes activeRepoFilter", () => {
    expect(SHORTCUTS_SRC).toContain("activeRepoFilter");
    expect(SHORTCUTS_SRC).toMatch(/activeRepoFilter\s*:\s*string\s*\|\s*null/);
  });

  it("'n' key handler guards on activeRepoFilter", () => {
    const nKeyStart = SHORTCUTS_SRC.indexOf('e.key === "n"');
    const nKeyBlock = SHORTCUTS_SRC.slice(nKeyStart, SHORTCUTS_SRC.indexOf("return;", nKeyStart) + 7);
    expect(nKeyBlock).toContain("activeRepoFilter");
    expect(nKeyBlock).toContain("return");
  });

  it("activeRepoFilter is in the useEffect dependency array", () => {
    const depsLine = SHORTCUTS_SRC.slice(SHORTCUTS_SRC.lastIndexOf("}, ["));
    expect(depsLine).toContain("activeRepoFilter");
  });
});

describe("StartRunModal.handleStart: fail fast when env/mounts set without repo", () => {
  it("handleStart checks !activeRepo before proceeding with env vars", () => {
    const fnStart = MODAL_SRC.indexOf("const handleStart");
    const fnEnd = MODAL_SRC.indexOf("\n  };", fnStart);
    const fnBlock = MODAL_SRC.slice(fnStart, fnEnd);
    expect(fnBlock).toContain("!activeRepo");
  });

  it("handleStart returns early when no repo but env vars are present", () => {
    const fnStart = MODAL_SRC.indexOf("const handleStart");
    const fnEnd = MODAL_SRC.indexOf("\n  };", fnStart);
    const fnBlock = MODAL_SRC.slice(fnStart, fnEnd);
    // Must have both the guard and a return
    const guardIdx = fnBlock.indexOf("!activeRepo");
    const guardBlock = fnBlock.slice(guardIdx, fnBlock.indexOf("return;", guardIdx) + 7);
    expect(guardBlock).toContain("return;");
  });

  it("handleStart sets an error when discarding env vars would occur", () => {
    const fnStart = MODAL_SRC.indexOf("const handleStart");
    const fnEnd = MODAL_SRC.indexOf("\n  };", fnStart);
    const fnBlock = MODAL_SRC.slice(fnStart, fnEnd);
    const guardIdx = fnBlock.indexOf("!activeRepo");
    const guardBlock = fnBlock.slice(guardIdx, fnBlock.indexOf("return;", guardIdx) + 7);
    expect(guardBlock).toContain("setEnvError(");
  });
});
