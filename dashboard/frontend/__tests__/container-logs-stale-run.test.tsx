/**
 * Regression test: ContainerLogs must not apply stale fetch results from a
 * previous run when the user switches runs quickly.
 *
 * Before the fix, refresh() awaited fetchContainerLogs() then immediately
 * called setLines() with no guard. If run A's fetch resolved after the user
 * switched to run B, run A's logs would overwrite run B's logs in state.
 *
 * The fix adds a genRef (useRef counter) that is incremented before the await
 * and checked after — stale results are discarded if gen !== genRef.current.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { ContainerLogs } from "@/components/logs/ContainerLogs";

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("ContainerLogs: stale fetch guard via generation counter", () => {
  it("source code declares genRef as a useRef", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/logs/ContainerLogs.tsx"),
      "utf-8",
    );

    expect(src).toContain("genRef = useRef(0)");
  });

  it("source code increments genRef before await in refresh()", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/logs/ContainerLogs.tsx"),
      "utf-8",
    );

    const refreshStart = src.indexOf("const refresh = useCallback");
    const refreshEnd = src.indexOf("}, [runId]);", refreshStart);
    const refreshBody = src.slice(refreshStart, refreshEnd);

    const genIncrPos = refreshBody.indexOf("++genRef.current");
    const awaitPos = refreshBody.indexOf("await ");
    const guardPos = refreshBody.indexOf("if (gen !== genRef.current) return");

    expect(genIncrPos).toBeGreaterThan(0);
    expect(awaitPos).toBeGreaterThan(genIncrPos);
    expect(guardPos).toBeGreaterThan(awaitPos);
  });

  it("source code checks gen before calling setLines", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/logs/ContainerLogs.tsx"),
      "utf-8",
    );

    const refreshStart = src.indexOf("const refresh = useCallback");
    const refreshEnd = src.indexOf("}, [runId]);", refreshStart);
    const refreshBody = src.slice(refreshStart, refreshEnd);

    const guardPos = refreshBody.indexOf("if (gen !== genRef.current) return");
    const setLinesPos = refreshBody.indexOf("setLines(");

    // Guard must come before setLines
    expect(guardPos).toBeGreaterThan(0);
    expect(setLinesPos).toBeGreaterThan(guardPos);
  });

  it("behavioral: switching run mid-fetch shows only the new run's logs", async () => {
    let resolveRunA!: (response: Response) => void;
    let resolveRunB!: (response: Response) => void;

    let callCount = 0;
    vi.stubGlobal("fetch", vi.fn(() => {
      callCount += 1;
      if (callCount === 1) {
        return new Promise<Response>((res) => { resolveRunA = res; });
      }
      return new Promise<Response>((res) => { resolveRunB = res; });
    }));

    const { rerender } = render(<ContainerLogs runId="run-a" />);

    // Switch to run-b before run-a's fetch resolves
    await act(async () => {
      rerender(<ContainerLogs runId="run-b" />);
    });

    // Now resolve run-a's fetch (stale — gen was for run-a)
    await act(async () => {
      resolveRunA(
        new Response(JSON.stringify({ lines: ["[run-a] log"], total: 1 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    // Resolve run-b's fetch (fresh)
    await act(async () => {
      resolveRunB(
        new Response(JSON.stringify({ lines: ["[run-b] log"], total: 1 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/\[run-b\] log/)).toBeInTheDocument();
    });

    // Run-a's log must NOT be visible — the stale result was discarded
    expect(screen.queryByText(/\[run-a\] log/)).not.toBeInTheDocument();
  });
});
