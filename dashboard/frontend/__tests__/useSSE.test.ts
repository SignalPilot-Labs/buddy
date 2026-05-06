/**
 * useSSE stale-run guard test.
 *
 * Verifies that callbacks from a superseded `connect()` call are dropped via
 * the generation counter, so fast run-switching cannot corrupt state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  fetchSseToken: vi.fn().mockResolvedValue("fake-token"),
  createSSE: vi.fn((...args: unknown[]) => new (globalThis.EventSource as unknown as new (url: string) => unknown)(`http://fake/sse?run=${args[0]}`)),
  pollEvents: vi.fn().mockResolvedValue({ events: [] }),
}));

import { useSSE } from "@/hooks/useSSE";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  listeners: Record<string, (e: MessageEvent) => void> = {};
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void): void {
    this.listeners[type] = handler;
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, data: unknown): void {
    const handler = this.listeners[type];
    if (handler) handler({ data: JSON.stringify(data) } as MessageEvent);
  }
}

/**
 * Regression: useSSE must compile without type errors.
 * The bug was `unknown || ""` yielding `{}` not `string` in processAudit.
 * This test verifies the module imports cleanly (TS compilation passes)
 * and the hook returns the expected shape.
 */
describe("useSSE type regression", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("hook returns events array with correct type", () => {
    const onRunEnded = vi.fn();
    const { result } = renderHook(() => useSSE(onRunEnded));
    expect(Array.isArray(result.current.events)).toBe(true);
    expect(result.current.events.length).toBe(0);
  });
});

describe("useSSE stale-run guard", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("drops events from a superseded connection after switching runs", async () => {
    const onRunEnded = vi.fn();
    const { result } = renderHook(() => useSSE(onRunEnded));

    // Connect to run A
    await act(async () => {
      await result.current.connect("run-a", { afterTool: 0, afterAudit: 0 });
    });
    const sseA = FakeEventSource.instances[0];
    expect(sseA).toBeDefined();
    expect(sseA.url).toContain("run-a");

    // Mark connected, then switch to run B before any events arrive
    act(() => {
      sseA.listeners.connected?.({ data: "{}" } as MessageEvent);
    });
    expect(result.current.connected).toBe(true);

    await act(async () => {
      await result.current.connect("run-b", { afterTool: 0, afterAudit: 0 });
    });
    const sseB = FakeEventSource.instances[1];
    expect(sseB).toBeDefined();
    expect(sseB.url).toContain("run-b");
    // run-a's EventSource should have been closed by the second connect
    expect(sseA.closed).toBe(true);

    // A laggy event from run A should NOT trigger onRunEnded for run B
    act(() => {
      sseA.emit("run_ended", { status: "completed" });
    });
    expect(onRunEnded).not.toHaveBeenCalled();

    // run B's run_ended fires correctly
    act(() => {
      sseB.listeners.connected?.({ data: "{}" } as MessageEvent);
      sseB.emit("run_ended", { status: "completed" });
    });
    expect(onRunEnded).toHaveBeenCalledTimes(1);
  });
});
