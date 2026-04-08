/**
 * NewRunButton states tests.
 *
 * Covers: disabled state and text content for all combinations of
 * agentReachable, isConfigured, and atCapacity — mirrors the conditional
 * logic in app/page.tsx lines 505-522.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Button } from "@/components/ui/Button";
import type { AgentHealth } from "@/lib/api";

interface NewRunButtonProps {
  agentHealth: AgentHealth | null;
  isConfigured: boolean;
}

function deriveStates(agentHealth: AgentHealth | null): {
  agentReachable: boolean;
  atCapacity: boolean;
} {
  const agentReachable =
    agentHealth != null && agentHealth.status !== "unreachable";
  const atCapacity =
    agentHealth !== null &&
    agentHealth !== undefined &&
    agentHealth.active_runs >= agentHealth.max_concurrent &&
    agentHealth.max_concurrent > 0;
  return { agentReachable, atCapacity };
}

function renderNewRunButton({ agentHealth, isConfigured }: NewRunButtonProps) {
  const { agentReachable, atCapacity } = deriveStates(agentHealth);

  const buttonText = !isConfigured
    ? "Setup Required"
    : !agentReachable
      ? "Offline"
      : atCapacity
        ? "At Capacity"
        : "New Run";

  const isDisabled = !agentReachable || !isConfigured || atCapacity;

  return render(
    <Button variant="success" size="md" disabled={isDisabled}>
      {buttonText}
    </Button>
  );
}

const IDLE_HEALTH: AgentHealth = {
  status: "idle",
  active_runs: 0,
  max_concurrent: 3,
  runs: [],
};

const UNREACHABLE_HEALTH: AgentHealth = {
  status: "unreachable",
  active_runs: 0,
  max_concurrent: 0,
  runs: [],
};

const AT_CAPACITY_HEALTH: AgentHealth = {
  status: "running",
  active_runs: 3,
  max_concurrent: 3,
  runs: [],
};

describe("NewRunButton states", () => {
  it('renders "New Run" when agent is reachable, configured, and below capacity', () => {
    renderNewRunButton({ agentHealth: IDLE_HEALTH, isConfigured: true });
    expect(screen.getByRole("button")).toHaveTextContent("New Run");
  });

  it('renders "Offline" when agent is unreachable', () => {
    renderNewRunButton({ agentHealth: UNREACHABLE_HEALTH, isConfigured: true });
    expect(screen.getByRole("button")).toHaveTextContent("Offline");
  });

  it('renders "At Capacity" when active_runs >= max_concurrent', () => {
    renderNewRunButton({ agentHealth: AT_CAPACITY_HEALTH, isConfigured: true });
    expect(screen.getByRole("button")).toHaveTextContent("At Capacity");
  });

  it('renders "Setup Required" when not configured', () => {
    renderNewRunButton({ agentHealth: IDLE_HEALTH, isConfigured: false });
    expect(screen.getByRole("button")).toHaveTextContent("Setup Required");
  });

  it("button is disabled when agent is unreachable", () => {
    renderNewRunButton({ agentHealth: UNREACHABLE_HEALTH, isConfigured: true });
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("button is disabled when at capacity", () => {
    renderNewRunButton({ agentHealth: AT_CAPACITY_HEALTH, isConfigured: true });
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("button is disabled when not configured", () => {
    renderNewRunButton({ agentHealth: IDLE_HEALTH, isConfigured: false });
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("button is enabled when agent is idle and configured", () => {
    renderNewRunButton({ agentHealth: IDLE_HEALTH, isConfigured: true });
    expect(screen.getByRole("button")).not.toBeDisabled();
  });
});
