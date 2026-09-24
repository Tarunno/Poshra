"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import Image from "next/image";
import { AlertCircle, ImagePlus, Sparkles, X } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  draftListingAction,
  type DraftState,
  type ListingDraft,
} from "@/lib/draft-actions";

const CONFIDENCE: Record<ListingDraft["confidence"], string> = {
  high: "",
  medium: "Read this one over — some of it is a guess.",
  low: "Check every field. The photograph or the notes were thin.",
};

function DraftButton({ disabled }: { disabled: boolean }) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="lg"
      className="rounded-full px-7"
      disabled={pending || disabled}
    >
      <Sparkles className="size-4" aria-hidden />
      {pending ? "Reading the photograph…" : "Draft the listing"}
    </Button>
  );
}

/**
 * Photograph in, draft out.
 *
 * Sits above the form rather than replacing it: what comes back is a first
 * attempt in the artisan's own fields, and she is the one who decides what the
 * shop sees. Nothing here saves anything.
 */
export function ListingDrafter({
  onDrafted,
}: {
  onDrafted: (draft: ListingDraft) => void;
}) {
  const [state, formAction] = useActionState(
    draftListingAction,
    {} as DraftState,
  );
  const [preview, setPreview] = useState<string>();
  const [notes, setNotes] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  // The action returns a draft; the form below is what fills from it. Handing
  // it over is an effect because it changes something outside this component,
  // and the identity of state.draft is what makes it happen once per draft
  // rather than on every render.
  useEffect(() => {
    if (state.draft) onDrafted(state.draft);
  }, [state.draft, onDrafted]);

  function choose(file: File | undefined) {
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return file ? URL.createObjectURL(file) : undefined;
    });
  }

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <p className="bg-background/70 text-ink-sky inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide uppercase">
          <Sparkles className="size-3.5" aria-hidden />
          Start from a photograph
        </p>
        <h2 className="mt-3 text-xl leading-snug font-bold tracking-tight text-balance">
          Photograph the piece and say what it is — in Bangla if you like.
        </h2>
        <p className="mt-1 text-sm opacity-70">
          You will get a listing in English to correct. Nothing is published
          until you save it.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-[160px_1fr]">
        <div>
          <input
            ref={fileRef}
            type="file"
            name="photo"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            onChange={(event) => choose(event.target.files?.[0])}
          />
          {preview ? (
            <div className="relative aspect-square overflow-hidden rounded-2xl">
              <Image
                src={preview}
                alt=""
                fill
                className="object-cover"
                unoptimized
              />
              <button
                type="button"
                aria-label="Remove the photograph"
                className="bg-background/90 absolute top-2 right-2 rounded-full p-1.5"
                onClick={() => {
                  if (fileRef.current) fileRef.current.value = "";
                  choose(undefined);
                }}
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="bg-background/60 hover:bg-background flex aspect-square w-full flex-col items-center justify-center gap-2 rounded-2xl border border-dashed text-sm opacity-70 transition-colors"
            >
              <ImagePlus className="size-6" aria-hidden />
              Add a photograph
            </button>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="notes">
            What is it? Describe it in your own words.
          </Label>
          <textarea
            id="notes"
            name="notes"
            rows={5}
            maxLength={2000}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="bg-background w-full rounded-xl border-0 p-4"
            placeholder="পাটের পাটি, ফরিদপুরে বোনা। নীল ডোরা। প্রায় দুই সপ্তাহ লেগেছে।"
          />
          <DraftButton disabled={!preview && notes.trim().length === 0} />
        </div>
      </div>

      {state.error && (
        <Alert variant="destructive" className="rounded-2xl">
          <AlertCircle className="size-4" />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      {state.draft && (
        <div className="bg-background/70 space-y-1 rounded-2xl p-4 text-sm">
          <p className="font-semibold">Filled in below — have a look.</p>
          {state.draft.price_reasoning && (
            <p className="opacity-70">{state.draft.price_reasoning}</p>
          )}
          {CONFIDENCE[state.draft.confidence] && (
            <p className="text-ink-rose font-medium">
              {CONFIDENCE[state.draft.confidence]}
            </p>
          )}
        </div>
      )}
    </form>
  );
}
