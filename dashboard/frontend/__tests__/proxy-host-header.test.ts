/**
 * Tests for the Host-header allowlist in the Next.js API proxy.
 *
 * The proxy rejects any inbound request whose Host header is not in the
 * loopback allowlist {"localhost:3400", "127.0.0.1:3400"} with HTTP 421
 * Misdirected Request, BEFORE any X-API-Key is attached.
 *
 * Strategy: the route module throws at import time if API_URL / DASHBOARD_API_KEY
 * are absent. We set them via vi.stubEnv and then load the module dynamically so
 * the stubs are in place before module evaluation.
 *
 * Host-header guard tests use `assertLoopbackHost` directly.
 * Forwarding tests mock global.fetch to confirm upstream call behaviour.
 */

import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";

// ── Stub env BEFORE module load ────────────────────────────────────────────────
// vi.stubEnv patches process.env before any dynamic import below, ensuring the
// fail-fast checks in route.ts pass during test evaluation.

vi.stubEnv("API_URL", "http://localhost:3401");
vi.stubEnv("DASHBOARD_API_KEY", "test-key-stub");

const STUB_API_KEY = "test-key-stub";

// ── Constants (mirror the module-level values) ─────────────────────────────────

const ALLOWED_HOST_LOOPBACK_NAME = "localhost:3400";
const ALLOWED_HOST_LOOPBACK_IP = "127.0.0.1:3400";
const STATUS_OK = 200;
const STATUS_MISDIRECTED = 421;

// ── Minimal request factory ────────────────────────────────────────────────────

/**
 * Creates a minimal object satisfying `headers.get(name)` used by
 * `assertLoopbackHost`. Using the standard Headers class avoids importing
 * next/server in tests.
 */
function makeReqWithHost(hostHeaderValue: string | null): { headers: Headers } {
  const headers = new Headers();
  if (hostHeaderValue !== null) {
    headers.set("host", hostHeaderValue);
  }
  return { headers } as { headers: Headers };
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("proxy host-header allowlist", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let assertLoopbackHost: (req: any) => Response | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let GET: (req: any, ctx: any) => Promise<Response>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let POST: (req: any, ctx: any) => Promise<Response>;

  beforeAll(async () => {
    // Env stubs are in place (vi.stubEnv above runs synchronously before this).
    const mod = await import("../app/api/[...path]/route");
    assertLoopbackHost = mod.assertLoopbackHost;
    GET = mod.GET;
    POST = mod.POST;
  });

  // ── Allowed hosts — assertLoopbackHost returns null ──────────────────────

  it("allows Host: localhost:3400", () => {
    const req = makeReqWithHost(ALLOWED_HOST_LOOPBACK_NAME);
    expect(assertLoopbackHost(req)).toBeNull();
  });

  it("allows Host: 127.0.0.1:3400", () => {
    const req = makeReqWithHost(ALLOWED_HOST_LOOPBACK_IP);
    expect(assertLoopbackHost(req)).toBeNull();
  });

  // RFC 3986 §3.2.2: host names are case-insensitive; we normalise to lowercase.
  it("allows Host: LOCALHOST:3400 (case-insensitive per RFC 3986)", () => {
    const req = makeReqWithHost("LOCALHOST:3400");
    expect(assertLoopbackHost(req)).toBeNull();
  });

  it("allows Host: LocalHost:3400 (mixed case)", () => {
    const req = makeReqWithHost("LocalHost:3400");
    expect(assertLoopbackHost(req)).toBeNull();
  });

  // ── Rejected hosts — assertLoopbackHost returns a 421 Response ───────────

  it("rejects Host: dashboard:3400 with 421", () => {
    const req = makeReqWithHost("dashboard:3400");
    const result = assertLoopbackHost(req);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(STATUS_MISDIRECTED);
  });

  it("rejects Host: 192.168.1.10:3400 (LAN IP) with 421", () => {
    const req = makeReqWithHost("192.168.1.10:3400");
    const result = assertLoopbackHost(req);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(STATUS_MISDIRECTED);
  });

  it("rejects Host: localhost:3401 (wrong port) with 421", () => {
    const req = makeReqWithHost("localhost:3401");
    const result = assertLoopbackHost(req);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(STATUS_MISDIRECTED);
  });

  it("rejects missing Host header with 421", () => {
    const req = makeReqWithHost(null);
    const result = assertLoopbackHost(req);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(STATUS_MISDIRECTED);
  });

  it("rejects Host: attacker.evil:3400 with 421", () => {
    const req = makeReqWithHost("attacker.evil:3400");
    const result = assertLoopbackHost(req);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(STATUS_MISDIRECTED);
  });

  // ── Full proxy integration: fetch mock verifies upstream call behaviour ───

  describe("fetch integration (upstream call behaviour)", () => {
    const upstreamMockResponse = new Response(JSON.stringify({ ok: true }), {
      status: STATUS_OK,
      headers: { "content-type": "application/json" },
    });

    beforeAll(() => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstreamMockResponse));
    });

    afterEach(() => {
      vi.clearAllMocks();
    });

    it("forwards to upstream and attaches X-API-Key when Host is localhost:3400", async () => {
      const req = new Request("http://localhost:3400/api/runs", {
        method: "GET",
        headers: { host: ALLOWED_HOST_LOOPBACK_NAME },
      });

      const res = await GET(req, { params: Promise.resolve({ path: ["runs"] }) });

      expect(res.status).toBe(STATUS_OK);
      expect(vi.mocked(fetch)).toHaveBeenCalledOnce();

      const forwardedHeaders = vi.mocked(fetch).mock.calls[0][1]
        ?.headers as Record<string, string>;
      expect(forwardedHeaders["X-API-Key"]).toBe(STUB_API_KEY);
    });

    it("forwards to upstream when Host is 127.0.0.1:3400", async () => {
      const req = new Request("http://127.0.0.1:3400/api/runs", {
        method: "GET",
        headers: { host: ALLOWED_HOST_LOOPBACK_IP },
      });

      const res = await GET(req, { params: Promise.resolve({ path: ["runs"] }) });

      expect(res.status).toBe(STATUS_OK);
      expect(vi.mocked(fetch)).toHaveBeenCalledOnce();
    });

    it("returns 421 for Host: dashboard:3400 without calling upstream or setting X-API-Key", async () => {
      const req = new Request("http://dashboard:3400/api/runs", {
        method: "GET",
        headers: { host: "dashboard:3400" },
      });

      const res = await GET(req, { params: Promise.resolve({ path: ["runs"] }) });

      expect(res.status).toBe(STATUS_MISDIRECTED);
      // Upstream must NOT have been reached.
      expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    });

    it("returns 421 for Host: 192.168.1.10:3400 without calling upstream", async () => {
      const req = new Request("http://192.168.1.10:3400/api/runs", {
        method: "POST",
        headers: {
          host: "192.168.1.10:3400",
          "content-type": "application/json",
        },
        body: JSON.stringify({ repo: "owner/repo" }),
      });

      const res = await POST(req, { params: Promise.resolve({ path: ["runs"] }) });

      expect(res.status).toBe(STATUS_MISDIRECTED);
      expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    });
  });
});
