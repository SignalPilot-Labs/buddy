/**
 * ControlBar component tests.
 *
 * Covers: button visibility by status, kill confirmation, busy state,
 * session lock display, and callback wiring.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ControlBar } from "@/components/controls/ControlBar";

function renderBar(overrides = {}) {
  const defaults = {
    status: "running" as const,
    onPause: vi.fn(),
    onResume: vi.fn(),
    onStop: vi.fn(),
    onKill: vi.fn(),
    onUnlock: vi.fn(),
    onToggleInject: vi.fn(),
    busy: false,
    sessionLocked: false,
    timeRemaining: null,
  };
  const props = { ...defaults, ...overrides };
  return { ...render(<ControlBar {...props} />), props };
}

describe("ControlBar", () => {
  it("shows Pause button when running", () => {
    renderBar({ status: "running" });
    expect(screen.getByText("Pause")).toBeInTheDocument();
  });

  it("calls onPause when Pause clicked", async () => {
    const { props } = renderBar({ status: "running" });
    await userEvent.click(screen.getByText("Pause"));
    expect(props.onPause).toHaveBeenCalledOnce();
  });

  it("Pause is disabled when paused", () => {
    renderBar({ status: "paused" });
    expect(screen.getByText("Pause").closest("button")).toBeDisabled();
  });

  it("Resume is enabled when paused", () => {
    renderBar({ status: "paused" });
    expect(screen.getByText("Resume").closest("button")).not.toBeDisabled();
  });

  it("calls onResume when Resume clicked", async () => {
    const { props } = renderBar({ status: "paused" });
    await userEvent.click(screen.getByText("Resume"));
    expect(props.onResume).toHaveBeenCalledOnce();
  });

  it("disables all buttons when busy", () => {
    renderBar({ status: "running", busy: true });
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("shows time remaining when session locked", () => {
    renderBar({ sessionLocked: true, timeRemaining: "25m" });
    expect(screen.getByText("25m")).toBeInTheDocument();
  });

  it("shows Unlock button when session locked", () => {
    renderBar({ sessionLocked: true, timeRemaining: "10m" });
    expect(screen.getByText("Unlock")).toBeInTheDocument();
  });

  it("hides Unlock when not locked", () => {
    renderBar({ sessionLocked: false });
    expect(screen.queryByText("Unlock")).not.toBeInTheDocument();
  });

  it("Kill requires double-click confirmation", async () => {
    const { props } = renderBar({ status: "running" });
    await userEvent.click(screen.getByText("Kill"));
    expect(props.onKill).not.toHaveBeenCalled();
    expect(screen.getByText("Confirm")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Confirm"));
    expect(props.onKill).toHaveBeenCalledOnce();
  });

  it("calls onStop when Stop clicked", async () => {
    const { props } = renderBar({ status: "running" });
    await userEvent.click(screen.getByText("Stop"));
    expect(props.onStop).toHaveBeenCalledOnce();
  });

  it("calls onToggleInject when Inject clicked", async () => {
    const { props } = renderBar({ status: "running" });
    await userEvent.click(screen.getByText("Inject"));
    expect(props.onToggleInject).toHaveBeenCalledOnce();
  });
});
