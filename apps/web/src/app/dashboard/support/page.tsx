import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft, Receipt, Search, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getCurrentUser } from "@/lib/api";
import { lookUpOrder } from "@/lib/checkout";
import { formatMoney } from "@/lib/format";

export const metadata = { title: "Look up an order — Poshra" };

function When({ at }: { at: string }) {
  return (
    <time dateTime={at} className="opacity-60">
      {new Date(at).toLocaleString("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      })}
    </time>
  );
}

/**
 * Answering somebody who has written in.
 *
 * A lookup and not a list, on purpose. Support arrives holding an order
 * number, so an order number is the only way in — there is no field here for
 * a name or an email, because a screen that answers "what has this person
 * been buying" is a screen that will eventually be used to. Checkout records
 * every lookup with who made it.
 */
export default async function SupportPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=%2Fdashboard%2Fsupport");
  if (user.role !== "admin") redirect("/dashboard");

  const params = await searchParams;
  const id = typeof params.id === "string" ? params.id.trim() : "";
  const found = id ? await lookUpOrder(id) : null;

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 text-sm font-semibold opacity-70 underline-offset-4 hover:underline hover:opacity-100"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Oversight
      </Link>

      <div>
        <p className="text-ink-sky text-sm font-semibold tracking-wide uppercase">
          Support
        </p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight">
          Look up an order.
        </h1>
        <p className="mt-2 max-w-2xl opacity-70">
          Paste the order number a customer gave you. There is no way to search
          by person here — and every lookup is recorded against your name.
        </p>
      </div>

      <form className="bg-tint-sky rounded-panel stitched flex flex-wrap items-end gap-3 p-5">
        <div className="min-w-[320px] flex-1 space-y-1">
          <label htmlFor="id" className="text-xs font-semibold opacity-70">
            Order number
          </label>
          <Input
            id="id"
            name="id"
            defaultValue={id}
            placeholder="0199c2f1-8a7e-7c31-b0d5-2f1a9e6c4b70"
            className="bg-background h-10 rounded-xl border-0 font-mono text-sm"
          />
        </div>
        <Button type="submit" size="sm" className="h-10 rounded-full px-5">
          <Search className="size-4" aria-hidden />
          Look it up
        </Button>
      </form>

      {id && !found && (
        <p className="flex items-center gap-2 opacity-70">
          <ShieldAlert className="size-4" aria-hidden />
          No order with that number.
        </p>
      )}

      {found && (
        <>
          <section className="bg-tint-lilac rounded-panel stitched p-6 sm:p-8">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold tracking-wide uppercase opacity-70">
                <Receipt className="size-4" aria-hidden />
                The order
              </h2>
              <span className="text-sm">
                <When at={found.order.created_at} />
              </span>
            </div>

            <p className="mt-3 font-mono text-xs break-all opacity-60">
              {found.order.id}
            </p>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="bg-background/60 rounded-2xl p-4">
                <p className="text-xs font-semibold tracking-wide uppercase opacity-60">
                  Status
                </p>
                <p className="mt-1 text-lg font-bold">{found.order.status}</p>
              </div>
              <div className="bg-background/60 rounded-2xl p-4">
                <p className="text-xs font-semibold tracking-wide uppercase opacity-60">
                  Total
                </p>
                <p className="mt-1 text-lg font-bold tabular-nums">
                  {formatMoney(found.order.total_minor, found.order.currency)}
                </p>
              </div>
              <div className="bg-background/60 rounded-2xl p-4">
                <p className="text-xs font-semibold tracking-wide uppercase opacity-60">
                  Payment
                </p>
                <p className="mt-1 font-mono text-xs break-all">
                  {found.order.payment_ref || found.order.failure_reason || "—"}
                </p>
              </div>
            </div>

            <ul className="mt-5 divide-y text-sm">
              {found.order.items.map((item) => (
                <li
                  key={item.sku_id}
                  className="flex items-baseline justify-between gap-3 py-2"
                >
                  <span className="min-w-0 truncate">
                    {item.quantity} × {item.title}
                  </span>
                  <span className="shrink-0 font-semibold tabular-nums">
                    {formatMoney(
                      item.unit_minor * item.quantity,
                      found.order.currency,
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="bg-tint-mint rounded-panel stitched p-6 sm:p-8">
            <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
              This buyer&rsquo;s other orders
            </h2>
            <p className="mt-1 text-sm opacity-60">
              Because &ldquo;has this happened before&rdquo; is the second
              question every time.
            </p>
            <ul className="mt-4 divide-y text-sm">
              {found.history.map((order) => (
                <li
                  key={order.id}
                  className="flex flex-wrap items-baseline justify-between gap-3 py-2"
                >
                  <Link
                    href={`/dashboard/support?id=${order.id}`}
                    className="font-mono text-xs break-all underline-offset-4 hover:underline"
                  >
                    {order.id}
                  </Link>
                  <span className="flex items-center gap-3">
                    <When at={order.created_at} />
                    <span className="opacity-70">{order.status}</span>
                    <span className="font-semibold tabular-nums">
                      {formatMoney(order.total_minor, order.currency)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
