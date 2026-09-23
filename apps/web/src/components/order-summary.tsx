import Link from "next/link";
import { Package } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Order } from "@/lib/checkout";
import { formatMoney } from "@/lib/format";

const tone: Record<string, "secondary" | "outline" | "destructive"> = {
  confirmed: "secondary",
  failed: "destructive",
};

/** One row in an order list: enough to recognise it, not the whole order. */
export function OrderSummary({ order }: { order: Order }) {
  const pieces = order.items.reduce((total, item) => total + item.quantity, 0);
  const placed = new Date(order.created_at).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <li>
      <Link
        href={`/orders/${order.id}`}
        className="hover:bg-background/50 -mx-3 flex flex-wrap items-center gap-4 rounded-2xl px-3 py-4 transition"
      >
        <Package className="size-4 shrink-0 opacity-50" aria-hidden />

        <div className="min-w-40 flex-1">
          <p className="text-sm font-semibold">
            {order.items[0]?.title ?? "Order"}
            {order.items.length > 1 && (
              <span className="font-normal opacity-70">
                {" "}
                and {order.items.length - 1} more
              </span>
            )}
          </p>
          <p className="text-xs opacity-70">
            {placed} · {pieces} {pieces === 1 ? "piece" : "pieces"}
          </p>
        </div>

        <Badge
          variant={tone[order.status] ?? "outline"}
          className="rounded-full capitalize"
        >
          {order.status}
        </Badge>

        <p className="w-28 text-right text-sm font-semibold tabular-nums">
          {formatMoney(order.total_minor, order.currency)}
        </p>
      </Link>
    </li>
  );
}
