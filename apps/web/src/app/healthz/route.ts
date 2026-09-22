/**
 * Liveness endpoint for Kubernetes.
 *
 * Deliberately trivial: it proves the Node server is up and answering, and
 * checks no dependency. If it called the API, an API outage would restart
 * every web pod instead of simply showing an error page.
 */
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
