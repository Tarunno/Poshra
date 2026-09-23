import Link from "next/link";
import { redirect } from "next/navigation";
import { Heart } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ProductGrid } from "@/components/product-grid";
import { apiFetch, getCurrentUser } from "@/lib/api";
import type { Product } from "@/lib/catalog";

export const metadata = { title: "Saved pieces — Poshra" };

export default async function SavedPage() {
  if (!(await getCurrentUser())) redirect("/login?next=%2Fsaved");

  const response = await apiFetch("/favourites");
  const body = response.ok
    ? ((await response.json()) as { results: Product[]; slugs: string[] })
    : { results: [], slugs: [] };

  if (body.results.length === 0) {
    return (
      <div className="bg-tint-rose rounded-panel stitched p-9 text-center">
        <Heart className="mx-auto size-8 opacity-40" aria-hidden />
        <h1 className="mt-4 text-2xl font-extrabold tracking-tight">
          Nothing saved yet.
        </h1>
        <p className="mt-2 text-sm opacity-70">
          Tap the heart on a piece and it waits for you here.
        </p>
        <Button asChild size="lg" className="mt-6 rounded-full px-7">
          <Link href="/shop">Browse the shop</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-extrabold tracking-tight">Saved pieces</h1>
      <ProductGrid
        products={body.results}
        saved={new Set(body.slugs)}
        actions
      />
    </div>
  );
}
