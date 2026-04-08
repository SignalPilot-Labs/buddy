/**
 * Capacity indicator logic tests.
 *
 * Tests the atCapacity derived state logic as a pure function.
 * No component rendering — just the boolean derivation.
 */

import { describe, it, expect } from "vitest";
import type { AgentHealth } from "@/lib/api";

const UNREACHABLE: AgentHealth = {
  status: "unreachable",
  active_runs: 0,
  max_concurrent: 0,
  runs: [],
};

function deriveAtCapacity(agentHealth: AgentHealth | null): boolean {
  return (
    agentHealth !== null &&
    agentHealth !== undefined &&
    agentHealth.active_runs >= agentHealth.max_concurrent &&
    agentHealth.max_concurrent > 0
  );
}

describe("atCapacity derived state", () => {
  it("is false when agentHealth is null", () => {
    expect(deriveAtCapacity(null)).toBe(false);
  });

  it("is false when active_runs is below max_concurrent", () => {
    const health: AgentHealth = {
      status: "running",
      active_runs: 2,
      max_concurrent: 5,
      runs: [],
    };
    expect(deriveAtCapacity(health)).toBe(false);
  });

  it("is true when active_runs equals max_concurrent", () => {
    const health: AgentHealth = {
      status: "running",
      active_runs: 5,
      max_concurrent: 5,
      runs: [],
    };
    expect(deriveAtCapacity(health)).toBe(true);
  });

  it("is true when active_runs exceeds max_concurrent", () => {
    const health: AgentHealth = {
      status: "running",
      active_runs: 6,
      max_concurrent: 5,
      runs: [],
    };
    expect(deriveAtCapacity(health)).toBe(true);
  });

  it("is false when agentHealth is unreachable (max_concurrent is 0)", () => {
    expect(deriveAtCapacity(UNREACHABLE)).toBe(false);
  });

  it("is false when active_runs is 0 and max_concurrent is 5", () => {
    const health: AgentHealth = {
      status: "idle",
      active_runs: 0,
      max_concurrent: 5,
      runs: [],
    };
    expect(deriveAtCapacity(health)).toBe(false);
  });

  it("is false when active_runs is 1 below max_concurrent", () => {
    const health: AgentHealth = {
      status: "running",
      active_runs: 4,
      max_concurrent: 5,
      runs: [],
    };
    expect(deriveAtCapacity(health)).toBe(false);
  });
});
