import type { NextConfig } from "next";

// Port must match config/config.yml → dashboard.api_port and lib/constants.ts
const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const apiUrl = process.env.API_URL || "http://localhost:3401";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
