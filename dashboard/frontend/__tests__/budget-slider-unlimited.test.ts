/**
 * Regression test: budget must be a single slider where 0 = unlimited.
 *
 * Before the fix, budget used a checkbox + slider — the checkbox was
 * confusing and inconsistent with other settings. Now it's a single
 * range input from 0 to 1000 where 0 means unlimited (no cap).
 *
 * The backend (autofyn/utils/models_http.py) treats max_budget_usd=0
 * as unlimited: it passes None to the SDK when budget is 0.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const MODAL_SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
  "utf-8",
);

describe("budget slider: 0 = unlimited, no checkbox", () => {
  it("does not use a budgetEnabled checkbox state", () => {
    expect(MODAL_SRC).not.toContain("budgetEnabled");
    expect(MODAL_SRC).not.toContain("setBudgetEnabled");
  });

  it("budget slider starts at min=0", () => {
    const rangeMatch = MODAL_SRC.match(/type="range"[^>]*min=\{(\d+)\}/);
    expect(rangeMatch).not.toBeNull();
    expect(rangeMatch![1]).toBe("0");
  });

  it("displays 'Unlimited' when budget is 0", () => {
    expect(MODAL_SRC).toContain('budget === 0 ? "Unlimited"');
  });

  it("budget state initializes to 0 (unlimited by default)", () => {
    expect(MODAL_SRC).toMatch(/useState\s*<?\s*\(?\s*0\s*\)?/);
    // Specifically check budget state init
    const budgetInit = MODAL_SRC.match(/const \[budget, setBudget\] = useState\((\d+)\)/);
    expect(budgetInit).not.toBeNull();
    expect(budgetInit![1]).toBe("0");
  });

  it("passes budget directly to onStart (no budgetEnabled ternary)", () => {
    const onStartCall = MODAL_SRC.slice(
      MODAL_SRC.indexOf("onStart(prompt"),
      MODAL_SRC.indexOf("onStart(prompt") + 200,
    );
    expect(onStartCall).not.toContain("budgetEnabled");
    // Budget is passed as-is (0 = unlimited)
    expect(onStartCall).toMatch(/,\s*budget\s*,/);
  });

  it("budgetSummary shows Unlimited for 0 and dollar amount otherwise", () => {
    expect(MODAL_SRC).toContain('budget > 0 ? `$${budget}` : "Unlimited"');
  });
});
