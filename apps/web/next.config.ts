import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every replica shares one cache, so revalidating a tag is observed by all
  // of them rather than only by the pod that handled the request. See
  // cache-handler.js for why that matters here.
  cacheHandler: require.resolve("./cache-handler.js"),
  // Without this the in-process LRU sits in front of Redis and keeps handing
  // back the entry another replica just invalidated — the exact bug this is
  // meant to fix.
  cacheMaxMemorySize: 0,
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
    // Next refuses to optimise images whose hostname resolves to a private
    // address, because an image optimiser that fetches arbitrary URLs is an
    // SSRF engine pointed at the internal network. Here the gateway *is* a
    // private address, and the patterns above already pin what may be fetched
    // to one host and one path prefix — our own public media route — so the
    // reachable set is not widened by allowing it. A deployment with a public
    // media hostname would not need this.
    dangerouslyAllowLocalIP: true,
  },
  /* config options here */
};

export default nextConfig;
