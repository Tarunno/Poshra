import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles only the files the server needs, so the runtime
  // image does not carry the whole node_modules tree.
  output: "standalone",
  images: {
    // Catalog photographs currently come from Wikimedia Commons. An explicit
    // allow-list keeps the image optimiser from being used as an open proxy.
    remotePatterns: [
      { protocol: "https", hostname: "thumb.wikimedia.org" },
      { protocol: "https", hostname: "upload.wikimedia.org" },
    ],
  },
  /* config options here */
};

export default nextConfig;
