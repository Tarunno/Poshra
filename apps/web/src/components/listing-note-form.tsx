"use client";

import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import { Archive, MessageSquarePlus, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { writeNoteAction, type NoteState } from "@/lib/oversight-actions";

const WORDING = {
  change_requested: "Ask for the change",
  archived: "Take it out",
  restored: "Put it back",
} as const;

function Submit({ kind }: { kind: keyof typeof WORDING }) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="sm"
      variant={kind === "archived" ? "destructive" : "default"}
      className="rounded-full"
      disabled={pending}
    >
      {pending ? "Sending…" : WORDING[kind]}
    </Button>
  );
}

/**
 * What an administrator can do about a listing: ask for a change, or take it
 * out of the shop. Both say why, and the artisan sees both.
 *
 * Archiving rather than deleting, and the wording says so — "take it out of
 * the shop" is what actually happens, and telling somebody their work was
 * deleted when it was hidden is a promise the database does not keep.
 */
export function ListingNoteForm({
  listingId,
  title,
  archived = false,
}: {
  listingId: string;
  title: string;
  /** An archived piece is offered the way back rather than another archiving. */
  archived?: boolean;
}) {
  const [state, formAction] = useActionState(writeNoteAction, {} as NoteState);
  const [kind, setKind] = useState<
    "change_requested" | "archived" | "restored"
  >(archived ? "restored" : "change_requested");
  const [open, setOpen] = useState(false);

  if (state.message) {
    return <p className="text-ink-mint text-xs font-medium">{state.message}</p>;
  }

  if (!open) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="rounded-full"
        onClick={() => setOpen(true)}
      >
        {archived ? (
          <Undo2 className="size-4" aria-hidden />
        ) : (
          <MessageSquarePlus className="size-4" aria-hidden />
        )}
        {archived ? "Put it back" : "Say something"}
      </Button>
    );
  }

  return (
    <form
      action={formAction}
      className="bg-background/70 space-y-2 rounded-2xl p-3"
    >
      <input type="hidden" name="listing_id" value={listingId} />
      <input type="hidden" name="kind" value={kind} />

      <div className="flex flex-wrap gap-2 text-xs">
        <button
          type="button"
          onClick={() => setKind("change_requested")}
          className={`rounded-full px-3 py-1 font-semibold ${
            kind === "change_requested"
              ? "bg-foreground text-background"
              : "bg-muted"
          }`}
        >
          Ask for a change
        </button>
        <button
          type="button"
          onClick={() => setKind("archived")}
          className={`inline-flex items-center gap-1 rounded-full px-3 py-1 font-semibold ${
            kind === "archived" ? "bg-ink-rose text-background" : "bg-muted"
          }`}
        >
          <Archive className="size-3" aria-hidden />
          Take out of the shop
        </button>
      </div>

      <label htmlFor={`reason-${listingId}`} className="sr-only">
        Why, for {title}
      </label>
      <textarea
        id={`reason-${listingId}`}
        name="reason"
        rows={2}
        maxLength={1000}
        required
        autoFocus
        placeholder={
          kind === "archived"
            ? "Why it is coming out of the shop. The artisan will read this."
            : kind === "restored"
              ? "Why it is going back — recorded beside the reason it came out."
              : "What needs to change. The artisan will read this."
        }
        className="bg-background w-full rounded-xl border-0 p-3 text-sm"
      />

      <div className="flex items-center gap-2">
        <Submit kind={kind} />
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-xs font-semibold opacity-60 underline-offset-4 hover:underline"
        >
          Cancel
        </button>
        {state.error && (
          <span role="alert" className="text-ink-rose text-xs font-medium">
            {state.error}
          </span>
        )}
      </div>
    </form>
  );
}
