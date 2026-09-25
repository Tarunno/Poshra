/**
 * Wiring the web tier into the collector.
 *
 * Next.js instruments itself once this file exists: a span for every request
 * it serves, and one for every server action, which is where most of the time
 * in this application actually goes. Without it the trace jumped from Kong
 * straight to whichever API the page called, and the rendering in between —
 * the slowest part of a server-rendered page — was a gap.
 *
 * Over OTLP HTTP rather than gRPC, which is what @vercel/otel speaks and what
 * the collector already listens for on 4318.
 */
import { registerOTel } from "@vercel/otel";

export function register() {
  // Unset in development and in a local build. Tracing that cannot be reached
  // should be off, not retrying in the background of every render.
  if (!process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return;

  registerOTel({ serviceName: "web" });
}
