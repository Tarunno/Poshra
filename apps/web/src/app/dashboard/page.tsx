import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowUpRight, MessagesSquare, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KanthaRule, MakersHand } from "@/components/motifs";
import { CraftPatch } from "@/components/craft-patch";
import { ActivityFeed } from "@/components/activity-feed";
import { OrderSummary } from "@/components/order-summary";
import { SalesChart } from "@/components/sales-chart";
import { WorkshopPiece } from "@/components/workshop-piece";
import { getCurrentUser } from "@/lib/api";
import { listMyProducts } from "@/lib/catalog";
import { listOrders } from "@/lib/checkout";
import { getSalesSummary } from "@/lib/sales";
import { formatMoney } from "@/lib/format";

export const metadata = { title: "Dashboard — Poshra" };

function Panel({
  title,
  href,
  cta,
  tint,
  children,
}: {
  title: string;
  href?: string;
  cta?: string;
  tint: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`${tint} rounded-panel stitched p-6 sm:p-8`}>
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
          {title}
        </h2>
        {href && (
          <Link
            href={href}
            className="inline-flex items-center gap-1 text-sm font-semibold underline-offset-4 hover:underline"
          >
            {cta}
            <ArrowUpRight className="size-4" aria-hidden />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

export default async function DashboardPage() {
  const user = await getCurrentUser();
  // Server-side guard. The gateway enforces access too; this is for UX.
  if (!user) redirect("/login?next=%2Fdashboard");

  const artisan = user.role === "artisan";

  // Independent fetches, so they run together: awaiting them in sequence would
  // add the slower one to the faster one for no reason.
  const [orders, listings, sales] = await Promise.all([
    listOrders(),
    artisan ? listMyProducts() : Promise.resolve([]),
    artisan ? getSalesSummary() : Promise.resolve(null),
  ]);

  const spent = orders.reduce((total, order) => total + order.total_minor, 0);
  const currency = orders[0]?.currency ?? "BDT";
  const needRestocking = listings.filter((piece) => piece.stock === 0);

  // The numbers read as a sentence rather than a row of tiles: a count only
  // means something next to what it is counting.
  const lines: string[] = [];
  if (artisan) {
    lines.push(
      listings.length === 1
        ? "One piece in your workshop"
        : `${listings.length} pieces in your workshop`,
    );
    if (needRestocking.length > 0) {
      lines.push(
        needRestocking.length === 1
          ? "one needs restocking"
          : `${needRestocking.length} need restocking`,
      );
    }
    if (sales && sales.pieces_sold > 0) {
      lines.push(
        `${sales.pieces_sold} sold for ${formatMoney(sales.revenue_minor, sales.currency)}`,
      );
    }
  }
  if (orders.length > 0) {
    lines.push(
      orders.length === 1
        ? `one order placed, ${formatMoney(spent, currency)}`
        : `${orders.length} orders placed, ${formatMoney(spent, currency)}`,
    );
  }

  return (
    <div className="space-y-6">
      <section className="bg-tint-saffron rounded-panel stitched relative overflow-hidden p-7 sm:p-9">
        <p className="text-xs font-semibold tracking-wide uppercase opacity-60">
          {artisan ? "Your workshop" : "Your account"}
        </p>
        <h1 className="mt-3 max-w-xl text-3xl leading-[1.1] font-extrabold tracking-tight text-balance sm:text-4xl">
          {user.full_name
            ? `Welcome back, ${user.full_name.split(" ")[0]}.`
            : "Welcome back."}
        </h1>
        <p className="mt-3 max-w-lg text-sm opacity-75">
          {lines.length > 0
            ? `${lines.join(" · ")}.`
            : artisan
              ? "Nothing listed yet. Photograph a piece, describe it, and it goes live."
              : "Nothing ordered yet — every piece here is made by hand, one at a time."}
        </p>
        {lines.length === 0 && !artisan && (
          <Button asChild size="lg" className="mt-6 rounded-full px-7">
            <Link href="/shop">Browse the shop</Link>
          </Button>
        )}
        {/* A patchwork square bleeding off the corner: the same motif the
            storefront uses, so the dashboard belongs to the same place. */}
        <span
          aria-hidden
          className="pointer-events-none absolute -top-10 -right-12 hidden sm:block"
        >
          <CraftPatch className="size-56 opacity-25" />
        </span>
      </section>

      {artisan && listings.length > 0 && (
        <Panel title="Pieces you make" tint="bg-tint-mint">
          <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {listings.slice(0, 5).map((piece) => (
              <WorkshopPiece key={piece.id} product={piece} />
            ))}
          </div>
          {listings.length > 5 && (
            <>
              <KanthaRule className="mt-6 h-3 w-full opacity-50" />
              <p className="mt-4 text-sm opacity-70">
                and {listings.length - 5} more in your workshop.
              </p>
            </>
          )}
        </Panel>
      )}

      {artisan && sales && sales.pieces_sold > 0 && (
        <Panel
          title={`Revenue, last ${sales.window_days} days`}
          tint="bg-tint-peach"
        >
          <div className="mt-4 grid gap-6 lg:grid-cols-[1.7fr_1fr]">
            <div>
              {/* The headline is a figure, not a one-bar chart: a single
                  value reads faster as a number. Proportional digits, not
                  tabular — equal widths make a large number look gappy, and
                  nothing is aligned under it. */}
              <p className="text-4xl font-extrabold sm:text-5xl">
                {formatMoney(sales.revenue_minor, sales.currency)}
              </p>
              <p className="mt-1 text-sm opacity-70">
                {sales.pieces_sold}{" "}
                {sales.pieces_sold === 1 ? "piece" : "pieces"} across{" "}
                {sales.orders} {sales.orders === 1 ? "order" : "orders"}
              </p>
              <SalesChart daily={sales.daily} currency={sales.currency} />
            </div>

            <div>
              <h3 className="text-sm font-semibold tracking-wide uppercase opacity-70">
                Best sellers
              </h3>
              <ol className="mt-4 space-y-3">
                {sales.top_pieces.map((piece, index) => (
                  <li
                    key={`${piece.slug ?? piece.title}`}
                    className="flex gap-3"
                  >
                    <span className="text-lg font-extrabold tabular-nums opacity-30">
                      {index + 1}
                    </span>
                    <span className="flex-1">
                      <span className="block text-sm leading-snug font-semibold">
                        {piece.slug ? (
                          <Link
                            href={`/products/${piece.slug}`}
                            className="underline-offset-4 hover:underline"
                          >
                            {piece.title}
                          </Link>
                        ) : (
                          piece.title
                        )}
                      </span>
                      <span className="block text-xs tabular-nums opacity-70">
                        {piece.pieces} sold ·{" "}
                        {formatMoney(piece.revenue_minor, sales.currency)}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Panel
          title="Recent orders"
          tint="bg-tint-lilac"
          href={orders.length > 0 ? "/orders" : "/shop"}
          cta={orders.length > 0 ? "See all" : "Browse"}
        >
          {orders.length > 0 ? (
            <ul className="divide-foreground/10 mt-2 divide-y">
              {orders.slice(0, 5).map((order) => (
                <OrderSummary key={order.id} order={order} />
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm opacity-70">
              Orders you place will appear here with their status and where the
              parcel is.
            </p>
          )}
        </Panel>

        <div className="space-y-6">
          {artisan && (
            <section className="bg-tint-peach rounded-panel stitched p-6 sm:p-7">
              <p className="bg-background/70 text-ink-peach inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide uppercase">
                <TrendingUp className="size-3.5" aria-hidden />
                Lately
              </p>
              <h2 className="mt-4 text-xl leading-snug font-bold tracking-tight text-balance">
                In your workshop
              </h2>
              <ActivityFeed sales={sales?.recent ?? []} />
              <MakersHand className="mt-4 size-7 opacity-30" />
            </section>
          )}

          <section className="bg-tint-sky rounded-panel stitched p-6 sm:p-7">
            <p className="bg-background/70 text-ink-sky inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide uppercase">
              <MessagesSquare className="size-3.5" aria-hidden />
              Assistant
            </p>
            <h2 className="mt-4 text-xl leading-snug font-bold tracking-tight text-balance">
              Ask in plain language
            </h2>
            <p className="mt-3 text-sm leading-relaxed italic opacity-75">
              {artisan
                ? "“Which pieces sold best this month, and what should I make next?”"
                : "“Find me a nakshi kantha under ৳12,000 that ships to Canada.”"}
            </p>
            <Badge variant="outline" className="mt-5 rounded-full">
              Being built
            </Badge>
          </section>
        </div>
      </div>
    </div>
  );
}
