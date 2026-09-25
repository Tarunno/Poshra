"use server";

/**
 * The only writes an administrator has: a note against a listing, and closing
 * one. Both go through the rate-limited public route, like every other write,
 * and both are refused by marketplace unless the role on the record allows it.
 */
import { revalidatePath } from "next/cache";

import { apiWriteFetch } from "./api";

export type NoteState = { message?: string; error?: string };

export async function writeNoteAction(
  _previous: NoteState,
  formData: FormData,
): Promise<NoteState> {
  const listingId = String(formData.get("listing_id") ?? "");
  const kind = String(formData.get("kind") ?? "change_requested");
  const reason = String(formData.get("reason") ?? "").trim();

  if (reason.length < 4) {
    // Said here as well as in the API, because a form that posts to be told
    // what it already knew is a form that wastes somebody's round trip.
    return {
      error: "Say what needs to change — the artisan has to answer it.",
    };
  }

  const response = await apiWriteFetch(
    `/oversight/listings/${listingId}/notes`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, reason }),
    },
  );

  if (!response.ok) {
    if (response.status === 403) return { error: "That needs an admin." };
    return { error: "The note could not be saved." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/dashboard/marketplace");
  return {
    message:
      kind === "archived"
        ? "Archived, and the artisan has been told why."
        : "The artisan has been asked.",
  };
}

export async function resolveNoteAction(
  _previous: NoteState,
  formData: FormData,
): Promise<NoteState> {
  const noteId = String(formData.get("note_id") ?? "");

  const response = await apiWriteFetch(`/oversight/notes/${noteId}/resolve`, {
    method: "POST",
  });
  if (!response.ok) return { error: "That note could not be closed." };

  revalidatePath("/dashboard");
  return { message: "Closed." };
}
