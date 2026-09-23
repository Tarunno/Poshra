"use server";

/**
 * Saving a piece.
 *
 * Whether *you* saved something is per-person, and the product list is cached
 * and shared by every visitor — so this is its own request rather than a field
 * on that list. Mixing them would hand one shopper's saved pieces to the next.
 */
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiFetch, apiWriteFetch } from "./api";

export type FavouriteState = { error?: string };

export async function toggleFavouriteAction(
  _prev: FavouriteState,
  formData: FormData,
): Promise<FavouriteState> {
  const slug = String(formData.get("slug") ?? "");
  // The button knows what it is looking at, so it says which way to move.
  const saved = String(formData.get("saved") ?? "") === "true";
  if (!slug) return {};

  const response = await apiWriteFetch(
    `/products/${encodeURIComponent(slug)}/favourite`,
    { method: saved ? "DELETE" : "POST" },
  );

  if (response.status === 401) {
    redirect(`/login?next=${encodeURIComponent(`/products/${slug}`)}`);
  }
  if (!response.ok) return { error: "That did not save. Try again." };

  // The hearts and the saved list both live under the layout.
  revalidatePath("/", "layout");
  return {};
}

/** The slugs this shopper saved, for marking hearts. Empty when signed out. */
export async function savedSlugs(): Promise<Set<string>> {
  try {
    const response = await apiFetch("/favourites");
    if (!response.ok) return new Set();
    const body = (await response.json()) as { slugs?: string[] };
    return new Set(body.slugs ?? []);
  } catch {
    return new Set();
  }
}
