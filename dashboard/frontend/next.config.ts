import type { NextConfig } from "next";

// Proxy lives in app/api/[...path]/route.ts — no rewrites needed.
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
