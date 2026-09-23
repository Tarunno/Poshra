import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { CheckCircle2, Package } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KanthaRule } from "@/components/motifs";
import { getCurrentUser } from "@/lib/api";
import { getOrder } from "@/lib/checkout";
import { formatMoney } from "@/lib/format";

export const metadata = { title: "Your order — Poshra" };

export default async function OrderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!(await getCurrentUser())) {
    redirect(`/login?next=${encodeURIComponent(`/orders/${id}`)}`);
  }

  const order = await getOrder(id);
  if (!order) notFound();

  const placed = new Date(order.created_at).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-6">
      <section className="bg-tint-mint rounded-panel stitched p-7 sm:p-9">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <CheckCircle2 className="text-ink-mint size-5" aria-hidden />
          Order confirmed
        </p>
        <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
          Thank you — your pieces are being prepared.
        </h1>
        <p className="mt-2 text-sm opacity-70">
          Placed on {placed} · Reference{" "}
          <span className="font-mono text-xs">{order.id}</span>
        </p>
      </section>

      <section className="bg-tint-saffron rounded-panel stitched p-6 sm:p-8">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
            What you ordered
          </h2>
          <Badge variant="secondary" className="rounded-full capitalize">
            {order.status}
          </Badge>
        </div>

        <ul className="divide-foreground/10 mt-4 divide-y">
          {order.items.map((item) => (
            <li
              key={item.sku_id}
              className="flex items-baseline gap-4 py-4 text-sm"
            >
              <Package className="size-4 shrink-0 opacity-50" aria-hidden />
              <div className="flex-1">
                <p className="font-semibold">{item.title}</p>
                <p className="opacity-70">by {item.artisan_name}</p>
              </div>
              <p className="tabular-nums opacity-70">× {item.quantity}</p>
              <p className="w-28 text-right font-semibold tabular-nums">
                {formatMoney(item.unit_minor * item.quantity, order.currency)}
              </p>
            </li>
          ))}
        </ul>

        <KanthaRule className="my-5 h-3 w-full opacity-50" />

        <div className="flex items-baseline justify-between">
          <span className="text-sm font-semibold">Total paid</span>
          <span className="text-2xl font-extrabold tabular-nums">
            {formatMoney(order.total_minor, order.currency)}
          </span>
        </div>
      </section>

      <Button asChild size="lg" className="rounded-full px-7">
        <Link href="/shop">Keep browsing</Link>
      </Button>
    </div>
  );
}
