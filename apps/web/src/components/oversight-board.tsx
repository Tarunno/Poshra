import Link from "next/link";
import {
  AlertTriangle,
  ImageOff,
  MessageSquareWarning,
  PackageX,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { AreaCurve, Dial, Sparkline, Trend } from "@/components/chart-parts";
import { Ranking } from "@/components/takings-chart";
import { formatMoney } from "@/lib/format";
import type { Overview, OversightListing } from "@/lib/oversight";

/** The last seven days against the seven before them. Both come out of the
 *  daily series the overview already returns, so a trend costs no extra query. */
function weekOnWeek(values: number[]) {
  const now = values.slice(-7).reduce((a, b) => a + b, 0);
  const before = values.slice(-14, -7).reduce((a, b) => a + b, 0);
  return { now, before };
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

/** A small card: a number, what it is, and how it is moving. */
function Stat({
  label,
  value,
  spark,
  trend,
  tone = "text-ink-mint",
}: {
  label: string;
  value: string | number;
  spark?: number[];
  trend?: { now: number; before: number };
  tone?: string;
}) {
  return (
    <div className="bg-background/70 rounded-2xl p-4">
      <p className="text-xs font-semibold tracking-wide uppercase opacity-55">
        {label}
      </p>
      <div className="mt-1 flex items-baseline gap-2">
        <p className="text-2xl font-extrabold tabular-nums">{value}</p>
        {trend && <Trend {...trend} />}
      </div>
      {spark && <Sparkline values={spark} className={tone} />}
    </div>
  );
}

/** One thing that needs doing, with the count and the way to it. */
function Attention({
  label,
  value,
  icon,
  href,
  tint,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  href?: string;
  tint: string;
}) {
  const quiet = value === 0;
  const body = (
    <div
      className={`flex items-center gap-3 rounded-2xl p-4 ${quiet ? "bg-background/50" : tint}`}
    >
      <span className={quiet ? "opacity-40" : "opacity-70"}>{icon}</span>
      <span className="text-2xl font-extrabold tabular-nums">{value}</span>
      <span className="text-sm leading-tight opacity-70">{label}</span>
    </div>
  );
  return href && !quiet ? (
    <Link href={href} className="block transition-transform hover:scale-[1.02]">
      {body}
    </Link>
  ) : (
    body
  );
}

/**
 * What an administrator opens the morning with.
 *
 * Laid out by importance rather than as a grid of equal tiles: the takings
 * curve is the largest thing because it answers "is this working", the dial
 * beside it answers "is the shop full", and the small numbers underneath
 * carry their own week-on-week so a count is never read alone.
 */
export function OversightBoard({ overview }: { overview: Overview }) {
  const { listings, sales, people, daily } = overview;

  const takings = daily.map((day) => day.takings_minor);
  const pieces = daily.map((day) => day.pieces);
  const takingsTrend = weekOnWeek(takings);
  const piecesTrend = weekOnWeek(pieces);
  const inTheShop = listings.total ? listings.published / listings.total : 0;
  const averageOrder = sales.orders
    ? Math.round(sales.takings_minor / sales.orders)
    : 0;
  const needsDoing =
    listings.without_photographs + listings.out_of_stock + overview.open_notes;

  return (
    <div className="space-y-6">
      {/* Takings, large, with the dial beside it. */}
      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="bg-tint-lilac rounded-panel stitched p-6 sm:p-8">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <div>
              <p className="text-xs font-semibold tracking-wide uppercase opacity-55">
                Taken · last {overview.window_days} days
              </p>
              <div className="mt-1 flex items-baseline gap-3">
                <p className="text-4xl font-extrabold tracking-tight tabular-nums">
                  {formatMoney(sales.takings_minor, "BDT")}
                </p>
                <Trend {...takingsTrend} />
              </div>
              <p className="mt-1 text-sm opacity-60">
                {sales.orders} orders · {sales.pieces} pieces ·{" "}
                {averageOrder ? formatMoney(averageOrder, "BDT") : "—"} an order
              </p>
            </div>
          </div>

          <AreaCurve values={takings} />
          <div className="flex justify-between text-xs opacity-50">
            <span>{daily[0]?.date}</span>
            <span>today</span>
          </div>
        </div>

        <div className="bg-tint-mint rounded-panel stitched flex flex-col justify-center gap-4 p-6 sm:p-8">
          <Dial
            share={inTheShop}
            label="of the catalogue is in the shop"
            caption={`${listings.published} of ${listings.total} listings`}
          />
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Drafts" value={listings.draft} />
            <Stat label="Archived" value={listings.archived} />
          </div>
        </div>
      </section>

      {/* Worth doing something about, as a row rather than a wall. */}
      <section className="bg-tint-saffron rounded-panel stitched p-6 sm:p-8">
        <h2 className="flex items-baseline gap-2 text-sm font-semibold tracking-wide uppercase opacity-70">
          Worth doing something about
          <span className="text-xs font-normal opacity-60">
            {needsDoing === 0 ? "nothing right now" : `${needsDoing} in all`}
          </span>
        </h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Attention
            label="listings with no photograph"
            value={listings.without_photographs}
            icon={<ImageOff className="size-5" aria-hidden />}
            href="/dashboard/marketplace?needs_photos=true"
            tint="bg-tint-rose"
          />
          <Attention
            label="in the shop with nothing left to sell"
            value={listings.out_of_stock}
            icon={<PackageX className="size-5" aria-hidden />}
            tint="bg-tint-peach"
          />
          <Attention
            label="notes waiting on an artisan"
            value={overview.open_notes}
            icon={<MessageSquareWarning className="size-5" aria-hidden />}
            href="/dashboard/marketplace"
            tint="bg-tint-lilac"
          />
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="bg-tint-sky rounded-panel stitched p-6 sm:p-8 lg:col-span-2">
          <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
            Selling most
          </h2>
          <div className="mt-4 grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xs font-semibold tracking-wide uppercase opacity-55">
                By artisan
              </h3>
              <Ranking
                rows={overview.top_artisans}
                empty="Nobody has sold anything yet."
              />
            </div>
            <div>
              <h3 className="text-xs font-semibold tracking-wide uppercase opacity-55">
                By craft
              </h3>
              <Ranking rows={overview.top_crafts} empty="No sales to rank." />
            </div>
          </div>
        </div>

        <div className="bg-tint-rose rounded-panel stitched space-y-3 p-6 sm:p-8">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold tracking-wide uppercase opacity-70">
            <Users className="size-4" aria-hidden />
            People
          </h2>
          <Stat
            label="Pieces sold a week"
            value={piecesTrend.now}
            spark={pieces}
            trend={piecesTrend}
            tone="text-ink-rose"
          />
          <div className="grid grid-cols-3 gap-2">
            <Stat label="Artisans" value={people.artisans} />
            <Stat label="Buyers" value={people.buyers} />
            <Stat label="New" value={people.joined_recently} />
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="bg-tint-mint rounded-panel stitched p-6 sm:p-8">
          <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
            Latest sales
          </h2>
          {overview.latest_sales.length === 0 ? (
            <p className="mt-3 text-sm opacity-60">
              Nothing has sold yet. The curve starts with the first order.
            </p>
          ) : (
            <ul className="mt-3 divide-y text-sm">
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
        </div>

        <div className="bg-tint-saffron rounded-panel stitched p-6 sm:p-8">
          <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
            Newest listings
          </h2>
          <ul className="mt-3 divide-y text-sm">
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
        </div>
      </section>
    </div>
  );
}

export { StatusTag };
