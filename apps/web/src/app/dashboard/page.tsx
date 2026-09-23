import Link from "next/link";
import { redirect } from "next/navigation";
import {
  ArrowUpRight,
  MessagesSquare,
  PackageOpen,
  ShoppingBag,
  TriangleAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ListingRow } from "@/components/listing-row";
import { OrderSummary } from "@/components/order-summary";
import { TintedCard } from "@/components/tinted-card";
import { getCurrentUser } from "@/lib/api";
import { listMyProducts } from "@/lib/catalog";
import { listOrders } from "@/lib/checkout";
import { formatMoney } from "@/lib/format";

export const metadata = { title: "Dashboard — Poshra" };

/** A number with a label: the dashboard's smallest unit. */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-background/60 rounded-2xl px-4 py-3">
      <p className="text-xs tracking-wide uppercase opacity-60">{label}</p>
      <p className="mt-1 text-xl font-extrabold tabular-nums">{value}</p>
    </div>
  );
}

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

  // Both fetches at once: they are independent, so waiting for them in
  // sequence would only add the slower one to the faster one.
  const [orders, listings] = await Promise.all([
    listOrders(),
    artisan ? listMyProducts() : Promise.resolve([]),
  ]);

  const spent = orders.reduce((total, order) => total + order.total_minor, 0);
  const currency = orders[0]?.currency ?? "BDT";
  const published = listings.filter((p) => p.status === "published");
  const outOfStock = listings.filter((p) => p.stock === 0);

  return (
    <div className="space-y-6">
      <section className="px-1 pt-2">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          {user.full_name
            ? `Welcome, ${user.full_name.split(" ")[0]}.`
            : "Welcome."}
        </h1>
        <p className="text-foreground/70 mt-2 text-sm">
          {user.email}{" "}
          <Badge variant="secondary" className="ml-1 rounded-full">
            {user.role}
          </Badge>
        </p>
      </section>

      {artisan && (
        <Panel title="Your workshop" tint="bg-tint-mint">
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Stat label="Listings" value={String(listings.length)} />
            <Stat label="Published" value={String(published.length)} />
            <Stat label="Out of stock" value={String(outOfStock.length)} />
          </div>

          {listings.length > 0 ? (
            <ul className="divide-foreground/10 mt-4 divide-y">
              {listings.slice(0, 6).map((product) => (
                <ListingRow key={product.id} product={product} />
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm opacity-70">
              You have not published anything yet.
            </p>
          )}

          {outOfStock.length > 0 && (
            <p className="text-ink-rose mt-4 flex items-center gap-2 text-sm font-medium">
              <TriangleAlert className="size-4" aria-hidden />
              {outOfStock.length}{" "}
              {outOfStock.length === 1 ? "piece is" : "pieces are"} out of stock
              and cannot be bought.
            </p>
          )}
        </Panel>
      )}

      <Panel
        title="Your orders"
        tint="bg-tint-saffron"
        href={orders.length > 0 ? "/orders" : undefined}
        cta="See all"
      >
        {orders.length > 0 ? (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Stat label="Orders placed" value={String(orders.length)} />
              <Stat label="Total spent" value={formatMoney(spent, currency)} />
            </div>
            <ul className="divide-foreground/10 mt-4 divide-y">
              {orders.slice(0, 4).map((order) => (
                <OrderSummary key={order.id} order={order} />
              ))}
            </ul>
          </>
        ) : (
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <p className="text-sm opacity-70">
              Nothing ordered yet — every piece is made by hand, one at a time.
            </p>
            <Button asChild size="sm" className="rounded-full px-5">
              <Link href="/shop">Browse the shop</Link>
            </Button>
          </div>
        )}
      </Panel>

      <div className="grid gap-5 sm:grid-cols-2">
        <TintedCard
          color="lilac"
          icon={PackageOpen}
          eyebrow={artisan ? "Next" : "Browse"}
          title={artisan ? "Sales and shipping" : "Discover crafts"}
          body={
            artisan
              ? "Which of your pieces sold, to where, and what is still to be sent. It needs a view built from the order events, which is the next thing being wired up."
              : "Handwoven, hand-painted and hand-thrown work from across Bangladesh."
          }
          href={artisan ? undefined : "/shop"}
          cta="Open the shop"
        >
          {artisan && (
            <Badge variant="outline" className="mt-5 rounded-full">
              Being built
            </Badge>
          )}
        </TintedCard>

        <TintedCard
          color="sky"
          icon={MessagesSquare}
          eyebrow="Assistant"
          title="Ask in plain language"
          body={
            artisan
              ? "“Which pieces sold best this month, and what should I make next?”"
              : "“Find me a nakshi kantha under ৳12,000 that ships to Canada.”"
          }
        >
          <Badge variant="outline" className="mt-5 rounded-full">
            Being built
          </Badge>
        </TintedCard>
      </div>

      {!artisan && (
        <p className="flex items-center gap-2 px-1 text-sm opacity-60">
          <ShoppingBag className="size-4" aria-hidden />
          Selling your own work? Ask us to turn on your workshop.
        </p>
      )}
    </div>
  );
}
