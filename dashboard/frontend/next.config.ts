import type { NextConfig } from "next";

// Port must match config/config.yml → dashboard.api_port and lib/constants.ts
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "avatars.githubusercontent.com", pathname: "/u/**" },
    ],
  },
  async rewrites() {
    const apiUrl = process.env.API_URL || "http://localhost:3401";
    return [
      // Dashboard API proxy (exclude auth routes handled by Next.js)
      {
        source: "/api/runs/:path*",
        destination: `${apiUrl}/api/runs/:path*`,
      },
      {
        source: "/api/agent/:path*",
        destination: `${apiUrl}/api/agent/:path*`,
      },
      {
        source: "/api/stream/:path*",
        destination: `${apiUrl}/api/stream/:path*`,
      },
      {
        source: "/api/settings/:path*",
        destination: `${apiUrl}/api/settings/:path*`,
      },
      {
        source: "/api/repos/:path*",
        destination: `${apiUrl}/api/repos/:path*`,
      },
    ];
  },
};

export default nextConfig;
