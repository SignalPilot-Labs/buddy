/**
 * Next.js App Router proxy — forwards /api/* to FastAPI with server-side X-API-Key.
 *
 * The browser never sees DASHBOARD_API_KEY. It is read once at module init (fail-fast)
 * and attached server-side to every forwarded request.
 *
 * CLI path: the `autofyn` CLI talks directly to FastAPI at http://localhost:3401 with
 * X-API-Key over the host loopback. It does NOT go through this proxy. Intentional —
 * routing CLI through :3400 would add a dependency on Next.js being up to stop/status
 * the stack.
 */

import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

// ── Env var name constants (no magic strings in the proxy body) ────────────────

const API_URL_ENV = "API_URL";
const DASHBOARD_API_KEY_ENV = "DASHBOARD_API_KEY";

// ── Header name constants ──────────────────────────────────────────────────────

const HEADER_X_API_KEY = "X-API-Key";
const HEADER_CONTENT_TYPE = "Content-Type";
const HEADER_ACCEPT = "Accept";
const HEADER_CACHE_CONTROL = "Cache-Control";
const HEADER_CONTENT_LENGTH = "content-length";

// ── Env reads — lazy at request time, not module load ─────────────────────────
// Next.js 16 collects page data during `next build` by evaluating route
// modules. Throwing at module-load would fail the build in CI where these
// env vars are not set. Read and validate at request time instead.

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

// ── Proxy helper ───────────────────────────────────────────────────────────────

interface RouteParams {
  params: Promise<{ path: string[] }>;
}

async function proxy(req: NextRequest, { params }: RouteParams): Promise<Response> {
  const upstreamBase = requireEnv(API_URL_ENV);
  const apiKey = requireEnv(DASHBOARD_API_KEY_ENV);

  const { path } = await params;
  const search = new URL(req.url).search;
  const targetUrl = `${upstreamBase}/api/${path.join("/")}${search}`;

  const forwardHeaders: Record<string, string> = {
    [HEADER_X_API_KEY]: apiKey,
  };

  const contentType = req.headers.get(HEADER_CONTENT_TYPE);
  if (contentType !== null) forwardHeaders[HEADER_CONTENT_TYPE] = contentType;

  const accept = req.headers.get(HEADER_ACCEPT);
  if (accept !== null) forwardHeaders[HEADER_ACCEPT] = accept;

  const cacheControl = req.headers.get(HEADER_CACHE_CONTROL);
  if (cacheControl !== null) forwardHeaders[HEADER_CACHE_CONTROL] = cacheControl;

  const isBodyMethod = req.method !== "GET" && req.method !== "HEAD";

  const fetchInit: RequestInit = {
    method: req.method,
    headers: forwardHeaders,
    ...(isBodyMethod ? { body: req.body, duplex: "half" } : {}),
  };

  const upstream = await fetch(targetUrl, fetchInit);

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete(HEADER_CONTENT_LENGTH);

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

// ── Exported method handlers ───────────────────────────────────────────────────

export function GET(req: NextRequest, ctx: RouteParams): Promise<Response> {
  return proxy(req, ctx);
}

export function POST(req: NextRequest, ctx: RouteParams): Promise<Response> {
  return proxy(req, ctx);
}

export function PUT(req: NextRequest, ctx: RouteParams): Promise<Response> {
  return proxy(req, ctx);
}

export function DELETE(req: NextRequest, ctx: RouteParams): Promise<Response> {
  return proxy(req, ctx);
}

export function PATCH(req: NextRequest, ctx: RouteParams): Promise<Response> {
  return proxy(req, ctx);
}

export function OPTIONS(req: NextRequest, ctx: RouteParams): Promise<Response> {
  return proxy(req, ctx);
}
