/**
 * A cache shared by every web replica.
 *
 * Next's default cache lives inside one process. With more than one replica
 * that is wrong in a specific, visible way: revalidating a tag clears the
 * cache on whichever pod handled the request, and the others keep serving
 * what they already had. An artisan who deleted a photograph would see it
 * again on the next page load, because a different pod answered.
 *
 * This puts the entries in Redis instead, so an invalidation is observed by
 * everyone. It is deliberately the plain `cacheHandler` rather than the newer
 * `cacheHandlers`: the catalog is cached through `fetch` with tags, and that
 * is what this one covers.
 *
 * Redis being unavailable must never take the site down — a cache is an
 * optimisation, and losing it means rendering again. Every operation here
 * fails soft.
 */
const { createClient } = require("redis");

// Long enough that nothing useful is evicted early, short enough that entries
// from a previous deploy do not sit here for ever: keys carry the build id, so
// after a release the old ones are unreachable and only waste memory.
const TTL_SECONDS = 60 * 60 * 24;

const PREFIX = "next:cache:";
const TAG_PREFIX = "next:tag:";

let clientPromise;

function client() {
  if (!clientPromise) {
    const url = process.env.REDIS_URL;
    if (!url) return Promise.resolve(null);

    const redis = createClient({
      url,
      socket: {
        connectTimeout: 2000,
        // Give up reconnecting aggressively; a slow cache is worse than none.
        reconnectStrategy: (retries) => Math.min(retries * 200, 5000),
      },
    });
    // Without a listener a connection error is an unhandled 'error' event,
    // which would take the server down over a cache being unreachable.
    redis.on("error", (error) => {
      console.warn("[cache] redis error:", error.message);
    });
    clientPromise = redis.connect().catch((error) => {
      console.warn("[cache] redis unavailable:", error.message);
      return null;
    });
  }
  return clientPromise;
}

/**
 * Cache entries contain Buffers (rendered HTML, RSC payloads, optimised
 * images), and JSON turns those into a shape that does not come back as a
 * Buffer. These two walk the structure and convert explicitly.
 */
function encode(value) {
  return JSON.stringify(value, (_key, item) => {
    if (item instanceof Buffer || item?.type === "Buffer") {
      const buffer = item instanceof Buffer ? item : Buffer.from(item.data);
      return { __buffer: buffer.toString("base64") };
    }
    return item;
  });
}

function decode(text) {
  return JSON.parse(text, (_key, item) => {
    if (item && typeof item === "object" && typeof item.__buffer === "string") {
      return Buffer.from(item.__buffer, "base64");
    }
    return item;
  });
}

module.exports = class SharedCacheHandler {
  constructor(options) {
    this.options = options;
  }

  async get(key) {
    try {
      const redis = await client();
      if (!redis) return null;

      const stored = await redis.get(PREFIX + key);
      // A miss is the normal answer, not an error: returning null makes Next
      // render and then call set().
      return stored ? decode(stored) : null;
    } catch (error) {
      console.warn("[cache] get failed:", error.message);
      return null;
    }
  }

  async set(key, data, ctx) {
    try {
      const redis = await client();
      if (!redis) return;

      const tags = ctx?.tags ?? [];
      const entry = { value: data, lastModified: Date.now(), tags };

      // The tag sets are what make invalidation cheap. Without them
      // revalidateTag would have to scan the keyspace, which is the one thing
      // you must not do to a Redis holding anything real.
      const pipeline = redis.multi();
      pipeline.set(PREFIX + key, encode(entry), { EX: TTL_SECONDS });
      for (const tag of tags) {
        pipeline.sAdd(TAG_PREFIX + tag, key);
        pipeline.expire(TAG_PREFIX + tag, TTL_SECONDS);
      }
      await pipeline.exec();
    } catch (error) {
      // The response has already been sent; losing the entry costs a render.
      console.warn("[cache] set failed:", error.message);
    }
  }

  async revalidateTag(tags) {
    const wanted = [tags].flat().filter(Boolean);
    if (wanted.length === 0) return;

    try {
      const redis = await client();
      if (!redis) return;

      for (const tag of wanted) {
        const keys = await redis.sMembers(TAG_PREFIX + tag);
        const pipeline = redis.multi();
        for (const key of keys) pipeline.del(PREFIX + key);
        pipeline.del(TAG_PREFIX + tag);
        await pipeline.exec();
      }
    } catch (error) {
      console.warn("[cache] revalidateTag failed:", error.message);
    }
  }

  // No per-request memory cache to clear: every read goes to Redis, which is
  // the point — a local copy would be the stale one again.
  resetRequestCache() {}
};
