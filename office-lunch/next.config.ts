import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return { beforeFiles: [{ source: "/api/:path*", destination: `${process.env.BACKEND_URL ?? "http://api:8000"}/api/:path*` }] };
  },
  output: "standalone",
  outputFileTracingRoot: path.resolve(__dirname),
  turbopack: { root: path.resolve(__dirname) },
};

export default nextConfig;
