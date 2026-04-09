/**
 * ContainerLogs component tests.
 *
 * Covers: empty state, loading, log display, filtering.
 */

import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ContainerLogs } from "@/components/logs/ContainerLogs";

const MOCK_LOGS = {
  lines: [
    "[server] INFO: Run started",
    "[core.loop] INFO: Round 1",
    "[core.loop] WARNING: Rate limited",
    "[core.loop] ERROR: Connection failed",
    "[sandbox] DEBUG: exec git status",
  ],
  total: 5,
};

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

function mockFetch(data: object) {
  return vi.fn(() =>
    Promise.resolve(new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }))
  );
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.stubGlobal("fetch", mockFetch(MOCK_LOGS));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("ContainerLogs", () => {
  it("shows empty state when no runId", () => {
    render(<ContainerLogs runId={null} />);
    expect(screen.getByText(/Select a run/i)).toBeInTheDocument();
  });

  it("loads and displays logs", async () => {
    render(<ContainerLogs runId="run-1" />);
    await waitFor(() => {
      expect(screen.getByText(/Run started/)).toBeInTheDocument();
    });
  });

  it("filters logs by text", async () => {
    render(<ContainerLogs runId="run-1" />);
    await waitFor(() => {
      expect(screen.getByText(/Run started/)).toBeInTheDocument();
    });

    await act(async () => {
      const filter = screen.getByPlaceholderText("Filter logs...");
      await userEvent.type(filter, "ERROR");
    });

    expect(screen.getByText(/Connection failed/)).toBeInTheDocument();
    expect(screen.queryByText(/Round 1/)).not.toBeInTheDocument();
  });

  it("shows no-logs state when API returns empty", async () => {
    vi.stubGlobal("fetch", mockFetch({ lines: [], total: 0 }));
    render(<ContainerLogs runId="run-1" />);
    await waitFor(() => {
      expect(screen.getByText(/No logs available/i)).toBeInTheDocument();
    });
  });
});
