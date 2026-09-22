/**
 * Catalog data access.
 *
 * Two fetch paths, deliberately separate:
 *
 * * `publicFetch` sends no cookies and its responses are cached and tagged, so
 *   the catalog is served from cache and one revalidation clears it. Sending
 *   credentials here would risk caching one person's view for everyone.
 * * `apiFetch` (lib/api.ts) forwards the session and never caches.
 *
 * Everything goes through the gateway, so the frontend cannot bypass auth,
 * rate limiting or tracing.
 */

const API_BASE =
  process.env.API_BASE_URL ?? "http://localhost:8080/api/marketplace";

export const CATALOG_TAG = "catalog";

export type Craft = {
  slug: string;
  name: string;
  name_bn: string;
  summary: string;
  description: string;
  home_division: string;
  home_district: string;
};

export type ArtisanSummary = {
  slug: string;
  display_name: string;
  division: string;
  district: string;
  is_verified: boolean;
};

export type Artisan = ArtisanSummary & {
  story: string;
  crafts: Craft[];
};

export type ProductImage = { url: string; alt_text: string; position: number };

export type Product = {
  id: string;
  slug: string;
  title: string;
  description: string;
  materials: string;
  dimensions: string;
  origin_district: string;
  price_minor: number;
  currency: string;
  stock: number;
  in_stock: boolean;
  lead_time_days: number;
  status: "draft" | "published" | "archived";
  artisan: ArtisanSummary;
  craft: Craft;
  images: ProductImage[];
  created_at: string;
};

export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type ProductQuery = {
  q?: string;
  craft?: string;
  artisan?: string;
  division?: string;
  min_price?: string;
  max_price?: string;
  in_stock?: string;
  limit?: number;
  offset?: number;
};

class CatalogError extends Error {
  constructor(
    readonly status: number,
    path: string,
  ) {
    super(`Catalog request failed: ${status} ${path}`);
    this.name = "CatalogError";
  }
}

async function publicFetch<T>(path: string, revalidate = 60): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    // No cookies: this response is shared by every visitor.
    next: { revalidate, tags: [CATALOG_TAG] },
    headers: { accept: "application/json" },
  });
  if (!response.ok) throw new CatalogError(response.status, path);
  return (await response.json()) as T;
}

function toQueryString(query: ProductQuery): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && `${value}`.length > 0) {
      params.set(key, `${value}`);
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function listProducts(query: ProductQuery = {}): Promise<Page<Product>> {
  return publicFetch<Page<Product>>(`/products${toQueryString(query)}`);
}

export function listCrafts(): Promise<Craft[]> {
  // The craft list changes rarely; a longer window keeps it out of the hot path.
  return publicFetch<Craft[]>("/crafts", 600);
}

/** Returns null for 404 so callers can render a proper not-found page. */
export async function getProduct(slug: string): Promise<Product | null> {
  try {
    return await publicFetch<Product>(`/products/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof CatalogError && error.status === 404) return null;
    throw error;
  }
}

export async function getArtisan(slug: string): Promise<Artisan | null> {
  try {
    return await publicFetch<Artisan>(`/artisans/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof CatalogError && error.status === 404) return null;
    throw error;
  }
}
