import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft, ImageOff, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ListingNoteForm } from "@/components/listing-note-form";
import { StatusTag } from "@/components/oversight-board";
import { getCurrentUser } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { listAllListings } from "@/lib/oversight";

export const metadata = { title: "Every listing — Poshra" };

/**
 * Every artisan's work in one table.
 *
 * The filters are in the query string rather than in component state: an
 * administrator who finds something wants to send somebody the link to it,
 * and a filtered view that cannot be linked is a view that gets described in
 * a message instead.
 */
export default async function MarketplaceListings({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=%2Fdashboard%2Fmarketplace");
  if (user.role !== "admin") redirect("/dashboard");

  const params = await searchParams;
  const one = (key: string) =>
    typeof params[key] === "string" ? (params[key] as string) : "";

  const filters = {
    q: one("q"),
    artisan: one("artisan"),
    status: one("status"),
    needs_photos: one("needs_photos"),
  };
  const { results, count } = await listAllListings(filters);

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 text-sm font-semibold opacity-70 underline-offset-4 hover:underline hover:opacity-100"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Oversight
      </Link>

      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-3xl font-extrabold tracking-tight">
          Every listing
        </h1>
        <p className="text-sm opacity-60">
          {count} {count === 1 ? "piece" : "pieces"}
          {filters.needs_photos === "true" && " with no photograph"}
        </p>
      </div>

      <form className="bg-tint-mint rounded-panel stitched flex flex-wrap items-end gap-3 p-5">
        <div className="min-w-[220px] flex-1 space-y-1">
          <label htmlFor="q" className="text-xs font-semibold opacity-70">
            Title or artisan
          </label>
          <Input
            id="q"
            name="q"
            defaultValue={filters.q}
            placeholder="kantha, Nasima…"
            className="bg-background h-10 rounded-xl border-0"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="status" className="text-xs font-semibold opacity-70">
            Status
          </label>
          <select
            id="status"
            name="status"
            defaultValue={filters.status}
            className="bg-background h-10 rounded-xl border-0 px-3"
          >
            <option value="">Any</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        <label className="flex h-10 items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="needs_photos"
            value="true"
            defaultChecked={filters.needs_photos === "true"}
          />
          No photograph
        </label>
        <Button type="submit" size="sm" className="h-10 rounded-full px-5">
          <Search className="size-4" aria-hidden />
          Filter
        </Button>
      </form>

      {results.length === 0 ? (
        <p className="opacity-70">Nothing matches that.</p>
      ) : (
        <div className="bg-tint-lilac rounded-panel stitched overflow-x-auto p-4 sm:p-6">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="text-xs tracking-wide uppercase opacity-55">
                <th className="px-3 py-2 text-left font-semibold">Piece</th>
                <th className="px-3 py-2 text-left font-semibold">Artisan</th>
                <th className="px-3 py-2 text-left font-semibold">Craft</th>
                <th className="px-3 py-2 text-right font-semibold">Price</th>
                <th className="px-3 py-2 text-right font-semibold">Stock</th>
                <th className="px-3 py-2 text-left font-semibold">Status</th>
                <th className="px-3 py-2 text-left font-semibold">
                  <span className="sr-only">Say something about it</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {results.map((piece) => (
                <tr key={piece.id} className="align-middle">
                  <td className="px-3 py-3">
                    <Link
                      href={`/products/${piece.slug}`}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {piece.title}
                    </Link>
                    {piece.photographs === 0 && (
                      <span className="text-ink-rose ml-2 inline-flex items-center gap-1 text-xs font-medium">
                        <ImageOff className="size-3.5" aria-hidden />
                        no photograph
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <Link
                      href={`/artisans/${piece.artisan_slug}`}
                      className="underline-offset-4 hover:underline"
                    >
                      {piece.artisan}
                    </Link>
                  </td>
                  <td className="px-3 py-3 opacity-70">{piece.craft}</td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    {formatMoney(piece.price_minor, piece.currency)}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    {piece.stock}
                  </td>
                  <td className="px-3 py-3">
                    <StatusTag status={piece.status} />
                  </td>
                  <td className="px-3 py-3">
                    <ListingNoteForm listingId={piece.id} title={piece.title} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
