/**
 * Regression tests for ContainerLogs autoScroll not reset on run switch (BUG 9).
 *
 * Root cause: The runId effect cleared lines, filter, and loading but did not
 * reset autoScroll. If the user had manually scrolled away from the bottom on
 * run A (setting autoScroll=false), then switched to run B, autoScroll stayed
 * false and new logs for run B would not auto-scroll.
 *
 * Fix: setAutoScroll(true) added to the runId effect so run switches always
 * start with auto-scroll enabled.
 */

import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ContainerLogs } from "@/components/logs/ContainerLogs";

const MOCK_LOGS_A = { lines: ["[run-a] INFO: started"], total: 1 };
const MOCK_LOGS_B = { lines: ["[run-b] INFO: started"], total: 1 };

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

function mockFetch(data: object) {
  return vi.fn(() =>
    Promise.resolve(
      new Response(JSON.stringify(data), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.stubGlobal("fetch", mockFetch(MOCK_LOGS_A));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("ContainerLogs: autoScroll reset on run switch (BUG 9)", () => {
  it("source code: runId effect contains setAutoScroll(true)", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/logs/ContainerLogs.tsx"),
      "utf-8",
    );

    // Find the runId effect (the one that calls setLines([]) and setFilter(""))
    const effectStart = src.indexOf("// Initial load");
    const effectEnd = src.indexOf("}, [runId, refresh]);", effectStart);
    const effectBody = src.slice(effectStart, effectEnd);

    expect(effectBody).toContain("setAutoScroll(true)");
  });

  it("source code: setAutoScroll(true) comes before setLoading(true) in the runId effect", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/logs/ContainerLogs.tsx"),
      "utf-8",
    );

    const effectStart = src.indexOf("// Initial load");
    const effectEnd = src.indexOf("}, [runId, refresh]);", effectStart);
    const effectBody = src.slice(effectStart, effectEnd);

    const autoScrollPos = effectBody.indexOf("setAutoScroll(true)");
    const loadingPos = effectBody.indexOf("setLoading(true)");

    expect(autoScrollPos).toBeGreaterThan(0);
    expect(loadingPos).toBeGreaterThan(0);
    expect(autoScrollPos).toBeLessThan(loadingPos);
  });

  it("behavioral: switching run resets autoScroll — 'Scroll to bottom' button is hidden", async () => {
    // Render component on run A and wait for logs
    vi.stubGlobal("fetch", mockFetch(MOCK_LOGS_A));
    const { rerender } = render(<ContainerLogs runId="run-a" />);

    await waitFor(() => {
      expect(screen.getByText(/run-a.*started/)).toBeInTheDocument();
    });

    // Simulate user scrolling away from bottom: autoScroll = false is set by handleScroll
    // We do this by firing a scroll event on the log container after the component
    // internally has scrollable content. We manipulate the DOM to fake scroll position.
    const logContainer = document.querySelector(".overflow-y-auto") as HTMLElement;
    expect(logContainer).toBeTruthy();

    // Fake the scroll position to be NOT at the bottom (> 40px from bottom)
    Object.defineProperty(logContainer, "scrollHeight", { value: 500, configurable: true });
    Object.defineProperty(logContainer, "scrollTop", { value: 0, configurable: true });
    Object.defineProperty(logContainer, "clientHeight", { value: 200, configurable: true });

    await act(async () => {
      logContainer.dispatchEvent(new Event("scroll"));
    });

    // "Scroll to bottom" button must now be visible (autoScroll = false)
    expect(screen.getByRole("button", { name: /scroll to bottom/i })).toBeInTheDocument();

    // Now switch to run B
    vi.stubGlobal("fetch", mockFetch(MOCK_LOGS_B));
    await act(async () => {
      rerender(<ContainerLogs runId="run-b" />);
    });

    await waitFor(() => {
      expect(screen.getByText(/run-b.*started/)).toBeInTheDocument();
    });

    // After run switch, autoScroll must have been reset to true
    // "Scroll to bottom" button must NOT be visible
    expect(screen.queryByRole("button", { name: /scroll to bottom/i })).not.toBeInTheDocument();
  });
});
