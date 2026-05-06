/**
 * Regression tests for ConnectionBanner debounce behavior.
 *
 * The banner must NOT flash during transient disconnects (e.g. run switches).
 * It waits CONNECTION_BANNER_DELAY_MS (5s) before showing, and clears
 * immediately when reconnected.
 */

import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ConnectionBanner } from "@/components/ui/ConnectionBanner";
import { CONNECTION_BANNER_DELAY_MS } from "@/lib/constants";

const NOOP_TOAST = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  NOOP_TOAST.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ConnectionBanner debounce", () => {
  it("does not show banner immediately when disconnected during active run", () => {
    render(
      <ConnectionBanner connectionState="disconnected" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows banner after CONNECTION_BANNER_DELAY_MS of continuous disconnect", () => {
    render(
      <ConnectionBanner connectionState="disconnected" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    act(() => {
      vi.advanceTimersByTime(CONNECTION_BANNER_DELAY_MS);
    });
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Disconnected/)).toBeInTheDocument();
  });

  it("does not show banner if reconnected before delay expires (run switch scenario)", () => {
    const { rerender } = render(
      <ConnectionBanner connectionState="disconnected" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    // Reconnect after 2s — well within the 5s grace period
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    rerender(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    // Advance past the original delay to confirm timer was cleared
    act(() => {
      vi.advanceTimersByTime(CONNECTION_BANNER_DELAY_MS);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("triggers exit and toast when reconnected after banner was shown", () => {
    const toastFn = vi.fn();
    // First connection (initial connect — no toast)
    const { rerender } = render(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={toastFn} selectedRunId="run-1" />,
    );
    expect(toastFn).not.toHaveBeenCalled();

    // Disconnect
    rerender(
      <ConnectionBanner connectionState="disconnected" runStatus="running" showToast={toastFn} selectedRunId="run-1" />,
    );
    act(() => {
      vi.advanceTimersByTime(CONNECTION_BANNER_DELAY_MS);
    });
    expect(screen.getByText(/Disconnected/)).toBeInTheDocument();

    // Reconnect — toast fires because this is a real reconnection
    rerender(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={toastFn} selectedRunId="run-1" />,
    );
    expect(toastFn).toHaveBeenCalledWith("Reconnected", "success");
  });

  it("shows reconnecting text when state is reconnecting after delay", () => {
    render(
      <ConnectionBanner connectionState="reconnecting" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    act(() => {
      vi.advanceTimersByTime(CONNECTION_BANNER_DELAY_MS);
    });
    expect(screen.getByText(/Reconnecting/)).toBeInTheDocument();
  });

  it("does not show banner for non-active run statuses", () => {
    render(
      <ConnectionBanner connectionState="disconnected" runStatus="completed" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    act(() => {
      vi.advanceTimersByTime(CONNECTION_BANNER_DELAY_MS);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not show banner when runStatus is null", () => {
    render(
      <ConnectionBanner connectionState="disconnected" runStatus={null} showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    act(() => {
      vi.advanceTimersByTime(CONNECTION_BANNER_DELAY_MS);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("fires reconnected toast when transitioning from disconnected to connected", () => {
    // Establish initial connection first
    const { rerender } = render(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    // Disconnect
    rerender(
      <ConnectionBanner connectionState="disconnected" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    act(() => {
      vi.advanceTimersByTime(CONNECTION_BANNER_DELAY_MS);
    });
    // Reconnect
    rerender(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={NOOP_TOAST} selectedRunId="run-1" />,
    );
    expect(NOOP_TOAST).toHaveBeenCalledWith("Reconnected", "success");
  });

  it("does not fire reconnected toast on initial SSE connection", () => {
    const toastFn = vi.fn();
    const { rerender } = render(
      <ConnectionBanner connectionState="disconnected" runStatus="running" showToast={toastFn} selectedRunId="run-1" />,
    );
    // First connect — should NOT show "Reconnected"
    rerender(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={toastFn} selectedRunId="run-1" />,
    );
    expect(toastFn).not.toHaveBeenCalled();
  });

  it("does not fire reconnected toast when switching runs", () => {
    const toastFn = vi.fn();
    // Connected to run-1
    const { rerender } = render(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={toastFn} selectedRunId="run-1" />,
    );
    // Switch to run-2: disconnect then connect
    rerender(
      <ConnectionBanner connectionState="disconnected" runStatus="running" showToast={toastFn} selectedRunId="run-2" />,
    );
    rerender(
      <ConnectionBanner connectionState="connected" runStatus="running" showToast={toastFn} selectedRunId="run-2" />,
    );
    // Should NOT toast — this is a new run, not a reconnection
    expect(toastFn).not.toHaveBeenCalled();
  });
});
