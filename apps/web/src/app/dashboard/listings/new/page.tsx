import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ListingForm } from "@/components/listing-form";
import { getCurrentUser } from "@/lib/api";
import { listCrafts } from "@/lib/catalog";

export const metadata = { title: "List a piece — Poshra" };

export default async function NewListingPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=%2Fdashboard%2Flistings%2Fnew");
  if (user.role !== "artisan" && user.role !== "admin") redirect("/dashboard");

  const crafts = await listCrafts();

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/listings"
        className="inline-flex items-center gap-1 text-sm font-semibold opacity-70 underline-offset-4 hover:underline hover:opacity-100"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Your listings
      </Link>

      <h1 className="text-3xl font-extrabold tracking-tight">List a piece</h1>

      <section className="bg-tint-lilac rounded-panel stitched p-6 sm:p-8">
        <ListingForm crafts={crafts} />
      </section>

      <p className="px-1 text-sm opacity-60">
        Photographs come next: save the listing, and you can add up to eight.
      </p>
    </div>
  );
}
