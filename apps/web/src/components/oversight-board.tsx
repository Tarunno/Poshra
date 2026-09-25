import Link from "next/link";
import { AlertTriangle, ImageOff, PackageX, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { formatMoney } from "@/lib/format";
import type { Overview, OversightListing } from "@/lib/oversight";

/**
 * What an administrator needs on opening the page.
 *
 * Two numbers are put first and given a colour, because they are the only two
 * anybody can act on this morning: listings with no photograph, and published
 * listings with nothing left to sell. The totals are context; these are work.
 */
function Count({
  label,
  value,
  tint = "",
  icon,
  href,
}: {
  label: string;
  value: number | string;
  tint?: string;
  icon?: React.ReactNode;
  href?: string;
}) {
  const body = (
    <div className={`rounded-2xl p-4 ${tint || "bg-background/60"}`}>
      <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wide uppercase opacity-60">
        {icon}
        {label}
      </p>
      <p className="mt-1 text-2xl font-extrabold tabular-nums">{value}</p>
    </div>
  );
  return href ? (
    <Link href={href} className="block transition-transform hover:scale-[1.02]">
      {body}
    </Link>
  ) : (
    body
  );
}

function StatusTag({ status }: { status: OversightListing["status"] }) {
  const tone =
    status === "published"
      ? "bg-tint-mint text-ink-mint"
      : status === "draft"
        ? "bg-tint-saffron text-ink-saffron"
        : "bg-muted opacity-70";
  return (
    <Badge variant="secondary" className={`rounded-full ${tone}`}>
      {status}
    </Badge>
  );
}

export function OversightBoard({ overview }: { overview: Overview }) {
  const { listings, sales, people } = overview;

  return (
    <div className="space-y-6">
      <section className="bg-tint-mint rounded-panel stitched p-6 sm:p-8">
        <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
          Worth doing something about
        </h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Count
            label="Listings with no photograph"
            value={listings.without_photographs}
            tint={listings.without_photographs > 0 ? "bg-tint-rose" : ""}
            icon={<ImageOff className="size-3.5" aria-hidden />}
            href="/dashboard/marketplace?needs_photos=true"
          />
          <Count
            label="In the shop, nothing left to sell"
            value={listings.out_of_stock}
            tint={listings.out_of_stock > 0 ? "bg-tint-saffron" : ""}
            icon={<PackageX className="size-3.5" aria-hidden />}
          />
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-4">
          <Count label="Listings" value={listings.total} />
          <Count label="In the shop" value={listings.published} />
          <Count label="Drafts" value={listings.draft} />
          <Count label="Archived" value={listings.archived} />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="bg-tint-lilac rounded-panel stitched p-6 sm:p-8">
          <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
            Sold · last {overview.window_days} days
          </h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Count label="Orders" value={sales.orders} />
            <Count label="Pieces" value={sales.pieces} />
            <Count
              label="Takings"
              value={formatMoney(sales.takings_minor, "BDT")}
            />
          </div>

          <h3 className="mt-6 text-xs font-semibold tracking-wide uppercase opacity-55">
            Latest sales
          </h3>
          {overview.latest_sales.length === 0 ? (
            <p className="mt-2 text-sm opacity-60">
              Nothing has sold yet. The counters start when an order is placed.
            </p>
          ) : (
            <ul className="mt-2 divide-y text-sm">
              {overview.latest_sales.slice(0, 6).map((sale) => (
                <li
                  key={`${sale.order_id}-${sale.sku_id}`}
                  className="flex items-baseline justify-between gap-3 py-2"
                >
                  <span className="min-w-0 truncate">
                    {sale.quantity} × {sale.title}
                    <span className="opacity-60"> · {sale.artisan}</span>
                  </span>
                  <span className="shrink-0 font-semibold tabular-nums">
                    {formatMoney(sale.line_minor, sale.currency)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-tint-sky rounded-panel stitched p-6 sm:p-8">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold tracking-wide uppercase opacity-70">
            <Users className="size-4" aria-hidden />
            People
          </h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Count label="Artisans" value={people.artisans} />
            <Count label="Buyers" value={people.buyers} />
            <Count label="Joined recently" value={people.joined_recently} />
          </div>

          <h3 className="mt-6 text-xs font-semibold tracking-wide uppercase opacity-55">
            Newest listings
          </h3>
          <ul className="mt-2 divide-y text-sm">
            {overview.latest_listings.slice(0, 6).map((piece) => (
              <li key={piece.id} className="flex items-center gap-3 py-2">
                <Link
                  href={`/products/${piece.slug}`}
                  className="min-w-0 flex-1 truncate underline-offset-4 hover:underline"
                >
                  {piece.title}
                  <span className="opacity-60"> · {piece.artisan}</span>
                </Link>
                {piece.photographs === 0 && (
                  <AlertTriangle
                    className="text-ink-rose size-4 shrink-0"
                    aria-label="no photograph"
                  />
                )}
                <StatusTag status={piece.status} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

export { StatusTag };
