/**
 * Unit tests for the Next.js /api proxy route handler.
 *
 * Strategy:
 * - Mock global fetch so no real network calls are made.
 * - Use vi.stubEnv + vi.resetModules + dynamic import to exercise
 *   the module-level fail-fast env checks.
 * - Verify that X-API-Key is attached server-side and that inbound
 *   X-API-Key headers from clients are stripped.
 * - Verify SSE response bodies are passed through as ReadableStream
 *   without buffering (Content-Length absent).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { NextRequest } from "next/server";

// ── Helpers ───────────────────────────────────────────────────────────────────

const TEST_API_URL = "http://localhost:3401";
const TEST_API_KEY = "test-key-abc123";

type RouteModule = typeof import("../app/api/[...path]/route");
type RouteHandler = (req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) => Promise<Response>;

function buildContext(pathStr: string): { params: Promise<{ path: string[] }> } {
  return { params: Promise.resolve({ path: pathStr.split("/") }) };
}

function makeNextRequest(opts: {
  method?: string;
  path?: string;
  search?: string;
  headers?: Record<string, string>;
  body?: ReadableStream<Uint8Array> | null;
}): NextRequest {
  const method = opts.method ?? "GET";
  const pathStr = opts.path ?? "foo";
  const search = opts.search ?? "";
  const url = `http://localhost:3400/api/${pathStr}${search}`;

  const headers: Record<string, string> = {
    host: "localhost:3400",
    ...opts.headers,
  };

  const reqInit: RequestInit & { duplex?: string } = {
    method,
    headers,
  };
  if (opts.body !== undefined) {
    reqInit.body = opts.body;
    if (opts.body instanceof ReadableStream) {
      reqInit.duplex = "half";
    }
  }

  return new Request(url, reqInit) as unknown as NextRequest;
}

function makeUpstreamResponse(opts: {
  status?: number;
  headers?: Record<string, string>;
  body?: ReadableStream<Uint8Array> | string | null;
}): Response {
  return new Response(opts.body ?? null, {
    status: opts.status ?? 200,
    headers: opts.headers,
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("Next.js /api proxy route", () => {
  beforeEach(() => {
    vi.stubEnv("API_URL", TEST_API_URL);
    vi.stubEnv("DASHBOARD_API_KEY", TEST_API_KEY);
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("throws at module import time when DASHBOARD_API_KEY is missing", async () => {
    vi.stubEnv("DASHBOARD_API_KEY", "");
    vi.resetModules();

    await expect(
      import("../app/api/[...path]/route"),
    ).rejects.toThrow("DASHBOARD_API_KEY is not set");
  });

  it("throws at module import time when API_URL is missing", async () => {
    vi.stubEnv("API_URL", "");
    vi.resetModules();

    await expect(
      import("../app/api/[...path]/route"),
    ).rejects.toThrow("API_URL is not set");
  });

  it("GET: calls upstream with correct URL and X-API-Key header", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeUpstreamResponse({ status: 200, body: "ok" }),
    );
    vi.stubGlobal("fetch", mockFetch);

    const mod: RouteModule = await import("../app/api/[...path]/route");
    const handler = mod.GET as RouteHandler;
    const req = makeNextRequest({ method: "GET", path: "runs" });

    await handler(req, buildContext("runs"));

    expect(mockFetch).toHaveBeenCalledOnce();
    const [calledUrl, calledInit] = mockFetch.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    expect(calledUrl).toBe(`${TEST_API_URL}/api/runs`);
    expect(calledInit.headers["X-API-Key"]).toBe(TEST_API_KEY);
  });

  it("forwards query string to upstream", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeUpstreamResponse({ status: 200, body: "[]" }),
    );
    vi.stubGlobal("fetch", mockFetch);

    const mod: RouteModule = await import("../app/api/[...path]/route");
    const handler = mod.GET as RouteHandler;
    const req = makeNextRequest({
      method: "GET",
      path: "runs",
      search: "?limit=10&status=running",
    });

    await handler(req, buildContext("runs"));

    const [calledUrl] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(calledUrl).toBe(`${TEST_API_URL}/api/runs?limit=10&status=running`);
  });

  it("POST: forwards body to upstream", async () => {
    const bodyContent = JSON.stringify({ prompt: "hello" });
    const encoder = new TextEncoder();
    const bodyStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(bodyContent));
        controller.close();
      },
    });

    const mockFetch = vi.fn().mockResolvedValue(
      makeUpstreamResponse({ status: 200, body: '{"ok":true}' }),
    );
    vi.stubGlobal("fetch", mockFetch);

    const mod: RouteModule = await import("../app/api/[...path]/route");
    const handler = mod.POST as RouteHandler;
    const req = makeNextRequest({
      method: "POST",
      path: "agent/start",
      headers: { "Content-Type": "application/json" },
      body: bodyStream,
    });

    await handler(req, buildContext("agent/start"));

    expect(mockFetch).toHaveBeenCalledOnce();
    const [, calledInit] = mockFetch.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    expect(calledInit.method).toBe("POST");
    expect(calledInit.body).toBeDefined();
    expect(calledInit.headers["X-API-Key"]).toBe(TEST_API_KEY);
  });

  it("returns upstream status and headers (no Content-Length)", async () => {
    const upstreamHeaders = {
      "Content-Type": "application/json",
      "content-length": "42",
      "X-Custom-Header": "value",
    };
    const mockFetch = vi.fn().mockResolvedValue(
      makeUpstreamResponse({
        status: 404,
        headers: upstreamHeaders,
        body: '{"detail":"not found"}',
      }),
    );
    vi.stubGlobal("fetch", mockFetch);

    const mod: RouteModule = await import("../app/api/[...path]/route");
    const handler = mod.GET as RouteHandler;
    const req = makeNextRequest({ method: "GET", path: "runs/missing" });

    const response = await handler(req, buildContext("runs/missing"));

    expect(response.status).toBe(404);
    expect(response.headers.get("X-Custom-Header")).toBe("value");
    expect(response.headers.get("content-length")).toBeNull();
  });

  it("SSE: passes ReadableStream body through without buffering", async () => {
    const sseStream = new ReadableStream<Uint8Array>();

    const mockFetch = vi.fn().mockResolvedValue(
      makeUpstreamResponse({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: sseStream,
      }),
    );
    vi.stubGlobal("fetch", mockFetch);

    const mod: RouteModule = await import("../app/api/[...path]/route");
    const handler = mod.GET as RouteHandler;
    const req = makeNextRequest({
      method: "GET",
      path: "stream/run-id-123",
      search: "?after_tool=0&after_audit=0",
    });

    const response = await handler(req, buildContext("stream/run-id-123"));

    expect(response.headers.get("content-type")).toBe("text/event-stream");
    // The body should be the same stream instance passed from upstream — not buffered.
    expect(response.body).toBe(sseStream);
    expect(response.headers.get("content-length")).toBeNull();
  });

  it("strips inbound X-API-Key header from client request", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeUpstreamResponse({ status: 200, body: "ok" }),
    );
    vi.stubGlobal("fetch", mockFetch);

    const mod: RouteModule = await import("../app/api/[...path]/route");
    const handler = mod.GET as RouteHandler;
    const req = makeNextRequest({
      method: "GET",
      path: "settings",
      headers: { "X-API-Key": "client-injected-bad-key" },
    });

    await handler(req, buildContext("settings"));

    const [, calledInit] = mockFetch.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    // Must use the server-side key, not the client-supplied one.
    expect(calledInit.headers["X-API-Key"]).toBe(TEST_API_KEY);
    expect(calledInit.headers["X-API-Key"]).not.toBe("client-injected-bad-key");
  });
});
