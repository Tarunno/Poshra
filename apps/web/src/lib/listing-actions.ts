"use server";

/**
 * Server Actions for an artisan's own listings.
 *
 * Ownership is never in the form. The gateway verifies the session and the API
 * takes the artisan from it, so a hidden field naming someone else's workshop
 * would be ignored — which is what stops one artisan listing work under
 * another's name.
 */
import { revalidatePath, updateTag } from "next/cache";
import { redirect } from "next/navigation";

import { apiWriteFetch } from "./api";
import { CATALOG_TAG } from "./catalog";
import { toMinorUnits } from "./money-input";

export type ListingState = {
  /** Field name → message, as the API reported it. */
  errors?: Record<string, string>;
  message?: string;
};

const CURRENCIES = new Set(["BDT", "USD", "EUR", "GBP"]);
const STATUSES = new Set(["draft", "published", "archived"]);

/**
 * The storefront is cached and tagged, so a change to a listing has to clear
 * it. updateTag rather than revalidateTag: an artisan who just saved should
 * see their own edit, not the stale copy served while a refresh runs behind it.
 */
function refreshCatalog() {
  updateTag(CATALOG_TAG);
  revalidatePath("/dashboard");
  revalidatePath("/dashboard/listings");
}

function text(formData: FormData, name: string): string {
  return String(formData.get(name) ?? "").trim();
}

/**
 * Flattens DRF's error shape into one message per field.
 *
 * It answers {"price_minor": ["Price must be greater than zero."]}, and
 * non-field problems arrive under "detail".
 */
function fieldErrors(body: unknown): Record<string, string> {
  if (typeof body !== "object" || body === null) return {};
  const errors: Record<string, string> = {};
  for (const [field, value] of Object.entries(
    body as Record<string, unknown>,
  )) {
    if (Array.isArray(value) && typeof value[0] === "string")
      errors[field] = value[0];
    else if (typeof value === "string") errors[field] = value;
  }
  return errors;
}

export async function saveListingAction(
  _prev: ListingState,
  formData: FormData,
): Promise<ListingState> {
  // Present when editing, absent when creating. It decides the method, so it
  // is the one thing the form has to carry.
  const slug = text(formData, "slug");

  const currency = text(formData, "currency").toUpperCase();
  if (!CURRENCIES.has(currency)) {
    return { errors: { currency: "Choose a currency." } };
  }

  const priceMinor = toMinorUnits(text(formData, "price"), currency);
  if (priceMinor === null || priceMinor <= 0) {
    return { errors: { price: "Enter a price like 5600 or 5600.50." } };
  }

  const stock = Number(text(formData, "stock"));
  if (!Number.isInteger(stock) || stock < 0) {
    return { errors: { stock: "Stock must be a whole number, zero or more." } };
  }

  const leadTime = Number(text(formData, "lead_time_days"));
  if (!Number.isInteger(leadTime) || leadTime < 0 || leadTime > 365) {
    return {
      errors: { lead_time_days: "Give a lead time between 0 and 365 days." },
    };
  }

  const status = text(formData, "status");
  if (!STATUSES.has(status)) {
    return { errors: { status: "Choose draft, published or archived." } };
  }

  const payload = {
    title: text(formData, "title"),
    craft: text(formData, "craft"),
    description: text(formData, "description"),
    materials: text(formData, "materials"),
    dimensions: text(formData, "dimensions"),
    origin_district: text(formData, "origin_district"),
    price_minor: priceMinor,
    currency,
    stock,
    lead_time_days: leadTime,
    status,
  };

  const response = await apiWriteFetch(
    slug ? `/products/${encodeURIComponent(slug)}` : "/products",
    {
      method: slug ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (response.status === 401) redirect("/login?next=%2Fdashboard%2Flistings");
  if (response.status === 403) {
    return { message: "Only an artisan with a workshop can publish listings." };
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const errors = fieldErrors(body);
    return Object.keys(errors).length > 0
      ? { errors }
      : { message: "Could not save the listing." };
  }

  refreshCatalog();
  redirect("/dashboard/listings?saved=1");
}

export async function setListingStatusAction(
  formData: FormData,
): Promise<void> {
  const slug = text(formData, "slug");
  const status = text(formData, "status");
  if (!slug || !STATUSES.has(status)) return;

  const response = await apiWriteFetch(
    `/products/${encodeURIComponent(slug)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
  if (response.status === 401) redirect("/login?next=%2Fdashboard%2Flistings");
  refreshCatalog();
}

export async function deleteListingAction(formData: FormData): Promise<void> {
  const slug = text(formData, "slug");
  if (!slug) return;

  const response = await apiWriteFetch(
    `/products/${encodeURIComponent(slug)}`,
    {
      method: "DELETE",
    },
  );
  if (response.status === 401) redirect("/login?next=%2Fdashboard%2Flistings");
  refreshCatalog();
}
