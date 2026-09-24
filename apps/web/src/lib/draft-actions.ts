"use server";

/**
 * Drafting a listing from a photograph and the artisan's own words.
 *
 * Goes through the public gateway route like the shopping assistant does:
 * every draft is a paid model call, and that route is the one carrying the
 * rate limiter and the session check. The photograph is forwarded as it
 * arrived rather than stored — nothing is written until the artisan saves the
 * listing herself.
 */
import { cookies } from "next/headers";

const ASSISTANT_BASE =
  process.env.ASSISTANT_BASE_URL ?? "http://localhost:8080/api/assistant";

export type ListingDraft = {
  title: string;
  description: string;
  materials: string;
  dimensions: string;
  craft: string;
  suggested_price_minor: number;
  price_reasoning: string;
  confidence: "high" | "medium" | "low";
};

export type DraftState = { draft?: ListingDraft; error?: string };

export async function draftListingAction(
  _previous: DraftState,
  formData: FormData,
): Promise<DraftState> {
  const photo = formData.get("photo");
  const notes = String(formData.get("notes") ?? "").trim();
  const hasPhoto = photo instanceof File && photo.size > 0;

  if (!hasPhoto && !notes) {
    return { error: "Add a photograph or describe the piece in a few words." };
  }

  // Rebuilt rather than forwarded whole: the form this came from also carries
  // the listing's own fields, and none of them are the model's business.
  const outgoing = new FormData();
  if (hasPhoto) outgoing.set("photo", photo);
  if (notes) outgoing.set("notes", notes);
  const craft = String(formData.get("craft") ?? "").trim();
  const district = String(formData.get("origin_district") ?? "").trim();
  if (craft) outgoing.set("craft", craft);
  if (district) outgoing.set("district", district);

  const cookieHeader = (await cookies()).toString();

  try {
    const response = await fetch(`${ASSISTANT_BASE}/draft-listing`, {
      method: "POST",
      // No Content-Type: fetch sets it with the multipart boundary, and
      // setting it by hand loses the boundary and the body with it.
      headers: cookieHeader ? { cookie: cookieHeader } : {},
      body: outgoing,
      cache: "no-store",
    });

    if (response.ok) {
      return { draft: (await response.json()) as ListingDraft };
    }

    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    if (response.status === 401) {
      return { error: "Sign in again to draft a listing." };
    }
    if (response.status === 413) {
      return {
        error: "That photograph is too large — six megabytes is plenty.",
      };
    }
    if (response.status === 415) {
      return { error: "A photograph has to be a JPEG, PNG or WebP." };
    }
    if (response.status === 429) {
      return {
        error: body.detail ?? "Every model is busy. Try again in a minute.",
      };
    }
    return {
      error:
        body.detail ?? "Drafting is unavailable right now — write it yourself.",
    };
  } catch {
    return { error: "The drafting service could not be reached." };
  }
}
