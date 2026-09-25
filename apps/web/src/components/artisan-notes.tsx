"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import Link from "next/link";
import { Archive, Check, MessageSquareWarning } from "lucide-react";

import { Button } from "@/components/ui/button";
import { resolveNoteAction, type NoteState } from "@/lib/oversight-actions";
import type { ListingNote } from "@/lib/oversight";

function Done() {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="sm"
      variant="secondary"
      className="rounded-full"
      disabled={pending}
    >
      <Check className="size-4" aria-hidden />
      {pending ? "…" : "Done"}
    </Button>
  );
}

/**
 * What has been asked of an artisan.
 *
 * Shown above their own work, because a note they do not see is a listing
 * quietly out of the shop and an artisan wondering why nothing sells. Closing
 * one is theirs to do: they are the one who knows whether it is done.
 */
export function ArtisanNotes({ notes }: { notes: ListingNote[] }) {
  const [state, formAction] = useActionState(
    resolveNoteAction,
    {} as NoteState,
  );
  if (notes.length === 0) return null;

  return (
    <section className="bg-tint-rose rounded-panel stitched p-6 sm:p-8">
      <h2 className="flex items-center gap-2 text-sm font-semibold tracking-wide uppercase opacity-70">
        <MessageSquareWarning className="size-4" aria-hidden />
        {notes.length === 1
          ? "One thing to look at"
          : `${notes.length} things to look at`}
      </h2>

      <ul className="mt-4 space-y-3">
        {notes.map((note) => (
          <li key={note.id} className="bg-background/70 rounded-2xl p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <Link
                href={`/dashboard/listings/${note.listing_slug}/edit`}
                className="font-semibold underline-offset-4 hover:underline"
              >
                {note.listing}
              </Link>
              {note.kind === "archived" && (
                <span className="text-ink-rose inline-flex items-center gap-1 text-xs font-semibold">
                  <Archive className="size-3.5" aria-hidden />
                  taken out of the shop
                </span>
              )}
            </div>
            <p className="mt-1 text-sm">{note.reason}</p>
            <form action={formAction} className="mt-3">
              <input type="hidden" name="note_id" value={note.id} />
              <Done />
            </form>
          </li>
        ))}
      </ul>

      {state.error && (
        <p role="alert" className="text-ink-rose mt-3 text-sm font-medium">
          {state.error}
        </p>
      )}
    </section>
  );
}
