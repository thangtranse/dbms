import path from "node:path";
import type { NextConfig } from "next";
import { existsSync, readFileSync } from "node:fs";

const infoPath = path.resolve(__dirname, "build-info.json");
const info = existsSync(infoPath) ? JSON.parse(readFileSync(infoPath, "utf8")) : {};

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_BUILD_VERSION: info.version ?? "unknown",
    NEXT_PUBLIC_BUILD_COMMIT: info.commit ?? "unknown",
    NEXT_PUBLIC_BUILD_SHORT_COMMIT: info.shortCommit ?? "unknown",
    NEXT_PUBLIC_BUILD_AT: info.builtAt ?? "",
    NEXT_PUBLIC_BUILD_DIRTY: info.dirty === true ? "true" : info.dirty === false ? "false" : "unknown",
  },
  async rewrites() {
    return { beforeFiles: [{ source: "/api/:path*", destination: `${process.env.BACKEND_URL ?? "http://api:8000"}/api/:path*` }] };
  },
  output: "standalone",
  outputFileTracingRoot: path.resolve(__dirname),
  turbopack: { root: path.resolve(__dirname) },
};

export default nextConfig;
