/**
 * API contract tests.
 *
 * Verifies that API functions send correct requests and handle responses.
 * Mocks fetch globally — no real HTTP.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  startRun,
  stopRun,
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
    await startRun("fix bugs", undefined, 10, 30, "main", "opus", "high", "owner/repo");
    expect(fetchCalls).toHaveLength(1);
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.prompt).toBe("fix bugs");
    expect(body.preset).toBeNull();
    expect(body.max_budget_usd).toBe(10);
    expect(body.duration_minutes).toBe(30);
    expect(body.base_branch).toBe("main");
    expect(body.model).toBe("opus");
    expect(body.effort).toBe("high");
    expect(body.repo).toBe("owner/repo");
  });

  it("sends preset key instead of prompt", async () => {
    await startRun(undefined, "security_hardening", 0, 0, "main", "opus", "high", null);
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.prompt).toBeNull();
    expect(body.preset).toBe("security_hardening");
  });

  it("returns run_id from response", async () => {
    const result = await startRun("test", undefined, 0, 0, "main", "sonnet", "high", null);
    expect(result.run_id).toBe("test-run-id");
  });

  it("sends null prompt and preset when both undefined", async () => {
    await startRun(undefined, undefined, 0, 0, "main", "opus-4-5", "medium", null);
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.prompt).toBeNull();
    expect(body.preset).toBeNull();
  });
});

describe("control signals use /api/runs/{run_id}/* endpoints", () => {
  it("stopRun hits /api/runs/{run_id}/stop with skip_pr in body", async () => {
    await stopRun("abc-123", true);
    expect(fetchCalls[0].url).toContain("/api/runs/abc-123/stop");
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.skip_pr).toBe(true);
  });

  it("stopRun sends skip_pr=false when opening a PR", async () => {
    await stopRun("abc-123", false);
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.skip_pr).toBe(false);
  });

  it("pauseAgent hits /api/runs/{run_id}/pause", async () => {
    await pauseAgent("abc-123");
    expect(fetchCalls[0].url).toContain("/api/runs/abc-123/pause");
  });

  it("resumeAgent hits /api/runs/{run_id}/resume", async () => {
    await resumeAgent("abc-123");
    expect(fetchCalls[0].url).toContain("/api/runs/abc-123/resume");
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body).toEqual({});
  });

  it("resumeAgent sends prompt as payload when provided", async () => {
    await resumeAgent("abc-123", "continue from where you left off");
    expect(fetchCalls[0].url).toContain("/api/runs/abc-123/resume");
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.payload).toBe("continue from where you left off");
  });

  it("resumeAgent sends empty body when prompt is undefined", async () => {
    await resumeAgent("abc-123", undefined);
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body).toEqual({});
  });

  it("unlockAgent hits /api/runs/{run_id}/unlock", async () => {
    await unlockAgent("abc-123");
    expect(fetchCalls[0].url).toContain("/api/runs/abc-123/unlock");
  });

  it("injectPrompt hits /api/runs/{run_id}/inject with payload", async () => {
    await injectPrompt("abc-123", "focus on tests");
    expect(fetchCalls[0].url).toContain("/api/runs/abc-123/inject");
    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.payload).toBe("focus on tests");
  });
});

describe("fetchAgentHealth", () => {
  it("returns unreachable on fetch error", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network"))));
    const health = await fetchAgentHealth();
    expect(health.status).toBe("unreachable");
    expect(health.runs).toEqual([]);
  });

  it("returns unreachable on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve(new Response("", { status: 500 }))
    ));
    const health = await fetchAgentHealth();
    expect(health.status).toBe("unreachable");
  });
});
