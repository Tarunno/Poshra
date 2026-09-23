/**
 * Guard for "where should we send the buyer next?" values.
 *
 * These arrive from a query string or a hidden form field, so they are user
 * input. An absolute URL here would turn any Poshra link into a bounce to
 * another host — the buyer sees our domain, lands somewhere else, and a
 * convincing fake sign-in page is one step away. Only a same-site path is
 * accepted; anything else falls back.
 */
export function safePath(value: string | undefined, fallback: string): string {
  if (!value) return fallback;
  // Must start with a single slash: "//evil.example" is protocol-relative and
  // "\\evil.example" is treated as one by some browsers.
  if (!value.startsWith("/") || value.startsWith("//")) return fallback;
  if (value.includes("\\")) return fallback;
  return value;
}
