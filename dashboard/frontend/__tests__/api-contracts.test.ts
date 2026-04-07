/**
 * API contract tests.
 *
 * Verifies that API functions send correct requests and handle responses.
 * Mocks fetch globally — no real HTTP.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  startRun,
  stopAgentInstant,
  killAgent,
  pauseAgent,
  resumeAgent,
  unlockAgent,
  injectPrompt,
  fetchAgentHealth,
} from "@/lib/api";

let fetchCalls: { url: string; init: RequestInit }[] = [];

beforeEach(() => {
  fetchCalls = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    fetchCalls.push({ url, init: init || {} });
    return Promise.resolve(new Response(
      JSON.stringify({ ok: true, run_id: "test-run-id", status: "idle", current_run_id: null }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
  }));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("startRun", () => {
  it("sends POST to /api/agent/start with all params", async () => {
    await startRun("fix bugs", 10, 30, "main", true);
    expect(fetchCalls).toHaveLength(1);
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.prompt).toBe("fix bugs");
    expect(body.max_budget_usd).toBe(10);
    expect(body.duration_minutes).toBe(30);
    expect(body.base_branch).toBe("main");
    expect(body.extended_context).toBe(true);
  });

  it("returns run_id from response", async () => {
    const result = await startRun("test", 0, 0, "main", false);
    expect(result.run_id).toBe("test-run-id");
  });

  it("sends null prompt when undefined", async () => {
    await startRun(undefined, 0, 0, "main", false);
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.prompt).toBeNull();
  });
});

describe("control signals with run_id", () => {
  it("stopAgentInstant appends run_id as query param", async () => {
    await stopAgentInstant("abc-123");
    expect(fetchCalls[0].url).toContain("run_id=abc-123");
  });

  it("stopAgentInstant works without run_id", async () => {
    await stopAgentInstant();
    expect(fetchCalls[0].url).not.toContain("run_id");
  });

  it("killAgent appends run_id", async () => {
    await killAgent("abc-123");
    expect(fetchCalls[0].url).toContain("run_id=abc-123");
  });

  it("pauseAgent appends run_id", async () => {
    await pauseAgent("abc-123");
    expect(fetchCalls[0].url).toContain("run_id=abc-123");
  });

  it("resumeAgent calls resume_signal endpoint", async () => {
    await resumeAgent("abc-123");
    expect(fetchCalls[0].url).toContain("resume_signal");
    expect(fetchCalls[0].url).toContain("run_id=abc-123");
  });

  it("unlockAgent appends run_id", async () => {
    await unlockAgent("abc-123");
    expect(fetchCalls[0].url).toContain("run_id=abc-123");
  });

  it("injectPrompt sends payload", async () => {
    await injectPrompt("abc-123", "focus on tests");
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.payload).toBe("focus on tests");
  });
});

describe("fetchAgentHealth", () => {
  it("returns unreachable on fetch error", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network"))));
    const health = await fetchAgentHealth();
    expect(health.status).toBe("unreachable");
    expect(health.current_run_id).toBeNull();
  });

  it("returns unreachable on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve(new Response("", { status: 500 }))
    ));
    const health = await fetchAgentHealth();
    expect(health.status).toBe("unreachable");
  });
});
