/**
 * Regression test: handleSetActive must refresh the repos list after activation.
 *
 * Before the fix, handleSetActive called fetchSettingsStatus() and fetchSettings()
 * but NOT fetchRepos(). The "Active" badge on the repo list depends on comparing
 * repo names against the settings.github_repo value — and even though setSettings()
 * updates that, the repos list (with its run counts, etc.) could be stale.
 *
 * Contrast with handleAddRepo and handleRemoveRepo which both call fetchRepos().
 * handleSetActive was inconsistent.
 *
 * The fix adds fetchRepos() to the Promise.all in handleSetActive and calls
 * setRepos(r) alongside the existing setStatus(s) and setSettings(cfg) calls.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../app/settings/page.tsx"),
  "utf-8",
);

describe("handleSetActive: must refresh repos list after activation", () => {
  it("handleSetActive calls fetchRepos inside Promise.all", () => {
    const fnStart = SRC.indexOf("handleSetActive");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBlock = SRC.slice(fnStart, fnEnd);
    expect(fnBlock).toContain("fetchRepos()");
  });

  it("handleSetActive calls setRepos with the result", () => {
    const fnStart = SRC.indexOf("handleSetActive");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBlock = SRC.slice(fnStart, fnEnd);
    expect(fnBlock).toContain("setRepos(");
  });

  it("handleSetActive fetches all three in a single Promise.all", () => {
    const fnStart = SRC.indexOf("handleSetActive");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBlock = SRC.slice(fnStart, fnEnd);
    const promiseAllBlock = fnBlock.slice(fnBlock.indexOf("Promise.all("));
    expect(promiseAllBlock).toContain("fetchSettingsStatus()");
    expect(promiseAllBlock).toContain("fetchSettings()");
    expect(promiseAllBlock).toContain("fetchRepos()");
  });
});
