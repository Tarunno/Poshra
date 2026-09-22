import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles only the files the server needs, so the runtime
  // image does not carry the whole node_modules tree.
  output: "standalone",
  /* config options here */
};

export default nextConfig;
