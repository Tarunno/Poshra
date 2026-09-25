/**
 * The marketplace seen from above.
 *
 * Read-only and administrators only, enforced in marketplace against the role
 * on the record rather than the header. This module only asks; a page that
 * renders nothing is what a non-admin gets, and the API would refuse them
 * anyway.
 */
import { apiFetch } from "./api";

export type OversightListing = {
  id: string;
  slug: string;
  title: string;
  status: "draft" | "published" | "archived";
  stock: number;
  price_minor: number;
  currency: string;
  artisan: string;
  artisan_slug: string;
  craft: string;
  origin_district: string;
  photographs: number;
  created_at: string;
};

export type OversightSale = {
  order_id: string;
  sku_id: string;
  title: string;
  artisan: string;
  quantity: number;
  line_minor: number;
  currency: string;
  occurred_at: string;
};

export type ListingNote = {
  id: string;
  kind: "change_requested" | "archived";
  reason: string;
  listing: string;
  listing_slug: string;
  author: string;
  created_at: string;
  resolved_at: string | null;
  is_open: boolean;
};

export type DailyTakings = {
  date: string;
  takings_minor: number;
  pieces: number;
};

export type Ranked = {
  name: string;
  slug?: string;
  takings_minor: number;
  pieces: number;
};

export type Overview = {
  window_days: number;
  daily: DailyTakings[];
  top_artisans: Ranked[];
  top_crafts: Ranked[];
  open_notes: number;
  listings: {
    total: number;
    published: number;
    draft: number;
    archived: number;
    without_photographs: number;
    out_of_stock: number;
  };
  sales: { orders: number; pieces: number; takings_minor: number };
  people: { artisans: number; buyers: number; joined_recently: number };
  latest_listings: OversightListing[];
  latest_sales: OversightSale[];
};

export type ListingFilters = {
  q?: string;
  artisan?: string;
  status?: string;
  needs_photos?: string;
};

export async function getOverview(): Promise<Overview | null> {
  try {
    const response = await apiFetch("/oversight/overview");
    if (!response.ok) return null;
    return (await response.json()) as Overview;
  } catch {
    return null;
  }
}

export async function listAllListings(
  filters: ListingFilters = {},
): Promise<{ results: OversightListing[]; count: number }> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) query.set(key, value);
  }
  query.set("limit", "40");

  try {
    const response = await apiFetch(`/oversight/listings?${query}`);
    if (!response.ok) return { results: [], count: 0 };
    return (await response.json()) as {
      results: OversightListing[];
      count: number;
    };
  } catch {
    return { results: [], count: 0 };
  }
}

/** What an artisan has been asked to do. Empty when nothing is waiting. */
export async function listMyNotes(): Promise<ListingNote[]> {
  try {
    const response = await apiFetch("/my/notes");
    if (!response.ok) return [];
    return (await response.json()) as ListingNote[];
  } catch {
    return [];
  }
}
