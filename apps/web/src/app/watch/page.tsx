import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PaharaConsole } from "@/components/pahara-console";
import { getCurrentUser } from "@/lib/api";

export const metadata = { title: "Pahara — Poshra" };

export default async function WatchPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=%2Fwatch");
  // A courtesy, not a control: Pahara checks the role itself, from a header
  // the gateway sets off the signed token. This only decides whether somebody
  // is shown a page they would be refused at.
  if (user.role !== "admin") redirect("/");

  return (
    <div className="space-y-6">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm font-semibold opacity-70 underline-offset-4 hover:underline hover:opacity-100"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Back to the shop
      </Link>

      <div>
        <p className="text-ink-mint text-sm font-semibold tracking-wide uppercase">
          পাহারা · the watch
        </p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight">
          Ask what the cluster has been doing.
        </h1>
        <p className="mt-2 max-w-2xl opacity-70">
          Pahara reads the traces, the logs and the metrics, and answers in
          sentences — with the queries it ran underneath, so every claim can be
          followed back to the thing it came from.
        </p>
      </div>

      <section className="bg-tint-mint rounded-panel stitched p-6 sm:p-8">
        <PaharaConsole
          grafanaUrl={
            process.env.GRAFANA_PUBLIC_URL ?? "http://192.168.110.203"
          }
        />
      </section>
    </div>
  );
}
