import Link from "next/link";
import { Coins } from "lucide-react";

import type { RecentSale } from "@/lib/sales";
import { formatMoney, formatRelativeTime } from "@/lib/format";

/**
 * What has happened in the workshop lately.
 *
 * Only sales for now, because those are the events this service consumes. The
 * shape is deliberately a feed rather than a table: an artisan reads it to know
 * what changed since they last looked, not to compare rows.
 */
export function ActivityFeed({ sales }: { sales: RecentSale[] }) {
  if (sales.length === 0) {
    return (
      <p className="mt-4 text-sm opacity-70">
        Nothing yet. Sales appear here moments after an order is placed.
      </p>
    );
  }

  return (
    <ul className="mt-4 space-y-1">
      {sales.map((sale) => (
        <li
          key={`${sale.order_id}-${sale.title}`}
          className="flex items-baseline gap-3 py-2"
        >
          <Coins
            className="text-ink-peach size-4 shrink-0 translate-y-0.5"
            aria-hidden
          />
          <p className="flex-1 text-sm leading-snug">
            Sold{" "}
            <span className="font-semibold tabular-nums">{sale.quantity}</span>{" "}
            ×{" "}
            {sale.slug ? (
              <Link
                href={`/products/${sale.slug}`}
                className="font-semibold underline-offset-4 hover:underline"
              >
                {sale.title}
              </Link>
            ) : (
              <span className="font-semibold">{sale.title}</span>
            )}{" "}
            <span className="opacity-70">
              for {formatMoney(sale.line_minor, sale.currency)}
            </span>
          </p>
          <time
            dateTime={sale.occurred_at}
            className="shrink-0 text-xs whitespace-nowrap opacity-60"
          >
            {formatRelativeTime(sale.occurred_at)}
          </time>
        </li>
      ))}
    </ul>
  );
}
