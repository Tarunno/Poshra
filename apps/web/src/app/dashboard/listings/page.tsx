import Link from "next/link";
import { redirect } from "next/navigation";
import { CheckCircle2, Plus, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getCurrentUser } from "@/lib/api";
import { listMyProducts } from "@/lib/catalog";
import { formatMoney } from "@/lib/format";
import {
  deleteListingAction,
  setListingStatusAction,
} from "@/lib/listing-actions";

export const metadata = { title: "Your listings — Poshra" };

export default async function ListingsPage({
  searchParams,
}: {
  searchParams: Promise<{ saved?: string; confirm?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=%2Fdashboard%2Flistings");
  if (user.role !== "artisan" && user.role !== "admin") redirect("/dashboard");

  const [{ saved, confirm }, listings] = await Promise.all([
    searchParams,
    listMyProducts(),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight">
          Your listings
        </h1>
        <Button asChild size="lg" className="rounded-full px-6">
          <Link href="/dashboard/listings/new">
            <Plus className="size-4" aria-hidden />
            List a piece
          </Link>
        </Button>
      </div>

      {saved && (
        <p className="flex items-center gap-2 text-sm font-medium">
          <CheckCircle2 className="text-ink-mint size-4" aria-hidden />
          Saved.
        </p>
      )}

      {listings.length === 0 ? (
        <div className="bg-tint-mint rounded-panel stitched p-9 text-center">
          <h2 className="text-2xl font-extrabold tracking-tight">
            Nothing listed yet.
          </h2>
          <p className="mt-2 text-sm opacity-70">
            Describe a piece you have made and it appears in the shop.
          </p>
          <Button asChild size="lg" className="mt-6 rounded-full px-7">
            <Link href="/dashboard/listings/new">List your first piece</Link>
          </Button>
        </div>
      ) : (
        <section className="bg-tint-mint rounded-panel stitched p-6 sm:p-8">
          <ul className="divide-foreground/10 divide-y">
            {listings.map((product) => (
              <li
                key={product.id}
                className="flex flex-wrap items-center gap-4 py-4"
              >
                <div className="min-w-48 flex-1">
                  <Link
                    href={`/products/${product.slug}`}
                    className="font-semibold underline-offset-4 hover:underline"
                  >
                    {product.title}
                  </Link>
                  <p className="text-xs opacity-70">
                    {product.craft.name} ·{" "}
                    {formatMoney(product.price_minor, product.currency)}
                  </p>
                </div>

                <p className="flex items-center gap-1 text-sm tabular-nums">
                  {product.stock === 0 && (
                    <TriangleAlert
                      className="text-ink-rose size-3.5"
                      aria-hidden
                    />
                  )}
                  <span
                    className={
                      product.stock === 0 ? "text-ink-rose" : "opacity-70"
                    }
                  >
                    {product.stock} left
                  </span>
                </p>

                <Badge
                  variant={
                    product.status === "published" ? "secondary" : "outline"
                  }
                  className="rounded-full capitalize"
                >
                  {product.status}
                </Badge>

                <div className="flex items-center gap-1">
                  <Button
                    asChild
                    variant="ghost"
                    size="sm"
                    className="rounded-full"
                  >
                    <Link href={`/dashboard/listings/${product.slug}/edit`}>
                      Edit
                    </Link>
                  </Button>

                  {/* Publishing and archiving are one field, so they are one
                      action with a different value rather than two endpoints. */}
                  <form action={setListingStatusAction}>
                    <input type="hidden" name="slug" value={product.slug} />
                    <input
                      type="hidden"
                      name="status"
                      value={
                        product.status === "published"
                          ? "archived"
                          : "published"
                      }
                    />
                    <Button
                      type="submit"
                      variant="ghost"
                      size="sm"
                      className="rounded-full"
                    >
                      {product.status === "published" ? "Archive" : "Publish"}
                    </Button>
                  </form>

                  {/* Deleting asks first, and asks through a link rather than
                      a dialog, so the confirmation works without JavaScript
                      and is a page you can back out of. */}
                  {confirm === product.slug ? (
                    <form
                      action={deleteListingAction}
                      className="flex items-center gap-1"
                    >
                      <input type="hidden" name="slug" value={product.slug} />
                      <span className="text-ink-rose text-xs font-semibold">
                        Delete for good?
                      </span>
                      <Button
                        type="submit"
                        variant="ghost"
                        size="sm"
                        className="text-ink-rose rounded-full"
                      >
                        Yes, delete
                      </Button>
                      <Button
                        asChild
                        variant="ghost"
                        size="sm"
                        className="rounded-full"
                      >
                        <Link href="/dashboard/listings">Keep it</Link>
                      </Button>
                    </form>
                  ) : (
                    <Button
                      asChild
                      variant="ghost"
                      size="sm"
                      className="text-ink-rose rounded-full"
                    >
                      <Link
                        href={`/dashboard/listings?confirm=${encodeURIComponent(product.slug)}`}
                      >
                        Delete
                      </Link>
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>

          <p className="mt-6 text-xs opacity-60">
            Archiving hides a piece but keeps it, along with everything it has
            sold. Deleting removes the listing for good.
          </p>
        </section>
      )}
    </div>
  );
}
