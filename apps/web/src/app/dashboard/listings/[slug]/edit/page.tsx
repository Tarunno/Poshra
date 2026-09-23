import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ListingForm } from "@/components/listing-form";
import { getCurrentUser } from "@/lib/api";
import { listCrafts, listMyProducts } from "@/lib/catalog";

export const metadata = { title: "Edit a listing — Poshra" };

export default async function EditListingPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const user = await getCurrentUser();
  if (!user) {
    redirect(
      `/login?next=${encodeURIComponent(`/dashboard/listings/${slug}/edit`)}`,
    );
  }
  if (user.role !== "artisan" && user.role !== "admin") redirect("/dashboard");

  const [crafts, mine] = await Promise.all([listCrafts(), listMyProducts()]);
  // Found among the caller's own listings, so someone else's slug is simply
  // not found here — the API would refuse the write anyway, but the page
  // should not pretend to offer it.
  const product = mine.find((candidate) => candidate.slug === slug);
  if (!product) notFound();

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/listings"
        className="inline-flex items-center gap-1 text-sm font-semibold opacity-70 underline-offset-4 hover:underline hover:opacity-100"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Your listings
      </Link>

      <h1 className="text-3xl font-extrabold tracking-tight text-balance">
        {product.title}
      </h1>

      <section className="bg-tint-lilac rounded-panel stitched p-6 sm:p-8">
        <ListingForm crafts={crafts} product={product} />
      </section>
    </div>
  );
}
