"use server";

/**
 * Photographs on a listing.
 *
 * The file is streamed straight through to the API rather than being read into
 * this process: a Server Action is an ordinary request handler, and buffering
 * every upload here would trade memory for nothing.
 */
import { updateTag } from "next/cache";
import { redirect } from "next/navigation";

import { apiWriteFetch } from "./api";
import { CATALOG_TAG } from "./catalog";

export type ImageState = { error?: string; added?: boolean };

export async function uploadImageAction(
  _prev: ImageState,
  formData: FormData,
): Promise<ImageState> {
  const slug = String(formData.get("slug") ?? "");
  const file = formData.get("file");

  if (!slug) return { error: "Save the listing before adding photographs." };
  if (!(file instanceof File) || file.size === 0) {
    return { error: "Choose a photograph first." };
  }

  const body = new FormData();
  body.set("file", file);
  const altText = String(formData.get("alt_text") ?? "").trim();
  if (altText) body.set("alt_text", altText.slice(0, 200));

  // No Content-Type header: fetch sets it with the multipart boundary, and
  // setting it by hand produces a body the server cannot parse.
  const response = await apiWriteFetch(
    `/products/${encodeURIComponent(slug)}/images`,
    { method: "POST", body },
  );

  if (response.status === 401) {
    redirect(
      `/login?next=${encodeURIComponent(`/dashboard/listings/${slug}/edit`)}`,
    );
  }
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    return { error: detail.detail ?? "That photograph could not be added." };
  }

  updateTag(CATALOG_TAG);
  return { added: true };
}

export async function deleteImageAction(formData: FormData): Promise<void> {
  const slug = String(formData.get("slug") ?? "");
  const imageId = String(formData.get("image_id") ?? "");
  if (!slug || !imageId) return;

  const response = await apiWriteFetch(
    `/products/${encodeURIComponent(slug)}/images/${encodeURIComponent(imageId)}`,
    { method: "DELETE" },
  );
  if (response.status === 401) {
    redirect(
      `/login?next=${encodeURIComponent(`/dashboard/listings/${slug}/edit`)}`,
    );
  }
  updateTag(CATALOG_TAG);
}
