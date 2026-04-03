import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextResponse } from "next/server";

// Mock auth to be a passthrough — it receives the callback and returns it as-is
vi.mock("@/lib/auth", () => ({
  auth: (callback: Function) => callback,
}));

import proxy, { config } from "@/proxy";

function makeRequest(pathname: string, isAuthenticated: boolean) {
  const url = new URL(pathname, "http://localhost:3000");
  return {
    auth: isAuthenticated ? { user: { id: "user-1" } } : null,
    nextUrl: url,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("proxy", () => {
  // 1. Unauthenticated user hitting /setup → redirected to /signin
  it("redirects unauthenticated user on /setup to /signin", () => {
    const response = proxy(makeRequest("/setup", false));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/signin");
  });

  // 2. Unauthenticated user hitting /setup/something → redirected to /signin
  it("redirects unauthenticated user on /setup/something to /signin", () => {
    const response = proxy(makeRequest("/setup/something", false));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/signin");
  });

  // 3. Authenticated user hitting /setup → passes through (NextResponse.next())
  it("allows authenticated user on /setup to pass through", () => {
    const response = proxy(makeRequest("/setup", true));
    expect(response.headers.get("location")).toBeNull();
  });

  // 4. Unprotected paths pass through for unauthenticated users
  it("passes through unauthenticated user on /signin", () => {
    const response = proxy(makeRequest("/signin", false));
    expect(response.headers.get("location")).toBeNull();
  });

  it("passes through unauthenticated user on /signup", () => {
    const response = proxy(makeRequest("/signup", false));
    expect(response.headers.get("location")).toBeNull();
  });

  it("passes through unauthenticated user on /api/auth paths", () => {
    const response = proxy(makeRequest("/api/auth/callback/github", false));
    expect(response.headers.get("location")).toBeNull();
  });

  // 5. config.matcher is defined
  it("config.matcher is defined and is an array", () => {
    expect(Array.isArray(config.matcher)).toBe(true);
    expect(config.matcher.length).toBeGreaterThan(0);
  });

  // 6. Unauthenticated user hitting / → redirected to /signin
  it("redirects unauthenticated user on / to /signin", () => {
    const response = proxy(makeRequest("/", false));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/signin");
  });

  // 7. Authenticated user hitting / → passes through
  it("allows authenticated user on / to pass through", () => {
    const response = proxy(makeRequest("/", true));
    expect(response.headers.get("location")).toBeNull();
  });
});
