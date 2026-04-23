/**
 * Regression test: handleStartRun must accept a `preset` parameter
 * in both the type definition (dashboardTypes.ts) and the implementation
 * (useRunActions.ts). The startRun API function (api.ts) must also
 * include preset in its signature.
 *
 * Catches the case where one layer adds preset but another forgets,
 * which causes a TS build failure only caught by `next build`.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const DASHBOARD_TYPES = fs.readFileSync(
  path.resolve(__dirname, "../hooks/dashboardTypes.ts"),
  "utf-8",
);

const USE_RUN_ACTIONS = fs.readFileSync(
  path.resolve(__dirname, "../hooks/useRunActions.ts"),
  "utf-8",
);

const API_TS = fs.readFileSync(
  path.resolve(__dirname, "../lib/api.ts"),
  "utf-8",
);

describe("handleStartRun preset parameter sync", () => {
  it("dashboardTypes.ts handleStartRun includes preset parameter", () => {
    // Find handleStartRun type blocks (there are two — RunActions and DashboardState)
    const matches = [...DASHBOARD_TYPES.matchAll(/handleStartRun[\s\S]*?\) => Promise<void>/g)];
    expect(matches.length).toBeGreaterThanOrEqual(2);
    for (const match of matches) {
      expect(match[0]).toContain("preset");
    }
  });

  it("useRunActions.ts handleStartRun implementation includes preset parameter", () => {
    const startIdx = USE_RUN_ACTIONS.indexOf("handleStartRun");
    const block = USE_RUN_ACTIONS.slice(startIdx, USE_RUN_ACTIONS.indexOf("handleInject"));
    expect(block).toContain("preset: string | undefined");
  });

  it("api.ts startRun function includes preset parameter", () => {
    const startIdx = API_TS.indexOf("export async function startRun");
    const block = API_TS.slice(startIdx, startIdx + 500);
    expect(block).toContain("preset");
  });
});
