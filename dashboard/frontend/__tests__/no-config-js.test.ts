/**
 * Static source-level checks that verify the browser-side API key plumbing has
 * been removed. These grep the source directly — no runtime needed.
 *
 * Rules verified:
 *  - app/layout.tsx must not load /config.js
 *  - lib/constants.ts must not contain the Window.__AUTOFYN_API_KEY__ declaration,
 *    getApiKey(), getApiBase(), or the API_KEY constant
 *  - lib/fetch.ts must not attach X-API-Key (case-insensitive)
 *  - lib/api.ts must not embed api_key= in any URL
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const ROOT = resolve(__dirname, "..");

function readSrc(rel: string): string {
  return readFileSync(resolve(ROOT, rel), "utf-8");
}

describe("no browser-side API key plumbing", () => {
  it("app/layout.tsx does not load /config.js", () => {
    const src = readSrc("app/layout.tsx");
    expect(src).not.toContain("/config.js");
  });

  it("lib/constants.ts does not contain __AUTOFYN_API_KEY__", () => {
    const src = readSrc("lib/constants.ts");
    expect(src).not.toContain("__AUTOFYN_API_KEY__");
  });

  it("lib/constants.ts does not contain getApiKey", () => {
    const src = readSrc("lib/constants.ts");
    expect(src).not.toContain("getApiKey");
  });

  it("lib/constants.ts does not contain getApiBase", () => {
    const src = readSrc("lib/constants.ts");
    expect(src).not.toContain("getApiBase");
  });

  it("lib/constants.ts does not export API_KEY constant", () => {
    const src = readSrc("lib/constants.ts");
    // Must not export the constant — the window-injected key is gone.
    expect(src).not.toContain("export const API_KEY");
  });

  it("lib/fetch.ts does not contain X-API-Key header (case-insensitive)", () => {
    const src = readSrc("lib/fetch.ts").toLowerCase();
    expect(src).not.toContain("x-api-key");
  });

  it("lib/api.ts does not embed api_key= in SSE URL", () => {
    const src = readSrc("lib/api.ts");
    expect(src).not.toContain("api_key=");
  });
});
