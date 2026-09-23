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
      // Photographs artisans upload, served from MinIO through the gateway.
      // A real deployment would name a hostname here rather than the LAN
      // address this cluster answers on.
      { protocol: "http", hostname: "192.168.110.201", pathname: "/media/**" },
      { protocol: "http", hostname: "localhost", pathname: "/media/**" },
    ],
  },
  /* config options here */
};

export default nextConfig;
