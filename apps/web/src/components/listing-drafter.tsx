"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import Image from "next/image";
import { AlertCircle, ImagePlus, Sparkles, X } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { VoiceNote } from "@/components/voice-note";
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
      className="rounded-full px-8"
      disabled={pending || disabled}
    >
      <Sparkles className="size-4" aria-hidden />
      {pending ? "Writing the listing…" : "Draft the listing"}
    </Button>
  );
}

/**
 * Speak, and get a listing back.
 *
 * Built around the microphone rather than around a form, because the artisan
 * this is for would not fill in a form in English. Everything else here is a
 * way of saying the same thing differently: a photograph if the words are
 * hard, typing if she would rather not speak.
 *
 * Nothing saves. What comes back fills the fields below, and she is the one
 * who decides what the shop sees.
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
  // Whether there is a recording to send. The clip itself lives in a file
  // input inside this form, because a Blob that is not in the form is a Blob
  // a server action never receives.
  const [spoke, setSpoke] = useState(false);
  const [typing, setTyping] = useState(false);
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

  const nothingYet = !preview && !spoke && notes.trim().length === 0;

  return (
    <form action={formAction} className="space-y-7">
      <div className="text-center">
        <p className="bg-background/70 text-ink-rose inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide uppercase">
          <Sparkles className="size-3.5" aria-hidden />
          পসরা · say it, and it is listed
        </p>
        <h2 className="mx-auto mt-3 max-w-md text-2xl leading-snug font-bold tracking-tight text-balance">
          Tell Poshra about the piece you made.
        </h2>
        <p className="mx-auto mt-2 max-w-sm text-sm opacity-70">
          Speak in Bangla. You will get a listing in English to correct —
          nothing is published until you save it.
        </p>
      </div>

      <VoiceNote onRecorded={setSpoke} />

      <div className="mx-auto max-w-md space-y-4">
        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-3">
          {/* The photograph is optional here: the listing takes its real
              photographs later. This one is for the model to look at. */}
          <input
            ref={fileRef}
            type="file"
            name="photo"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            onChange={(event) => choose(event.target.files?.[0])}
          />
          {preview ? (
            <div className="relative size-16 shrink-0 overflow-hidden rounded-2xl">
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
                className="bg-background/90 absolute top-1 right-1 rounded-full p-1"
                onClick={() => {
                  if (fileRef.current) fileRef.current.value = "";
                  choose(undefined);
                }}
              >
                <X className="size-3" aria-hidden />
              </button>
            </div>
          ) : (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="rounded-full"
              onClick={() => fileRef.current?.click()}
            >
              <ImagePlus className="size-4" aria-hidden />
              Add a photograph
            </Button>
          )}

          {preview && (
            <p className="text-sm opacity-70">
              Poshra will look at this while it writes.
            </p>
          )}

          {!typing && (
            <button
              type="button"
              onClick={() => setTyping(true)}
              className="text-sm font-semibold underline-offset-4 hover:underline"
            >
              or type it instead
            </button>
          )}
        </div>

        {typing && (
          <div className="space-y-2">
            <label htmlFor="notes" className="text-sm font-semibold">
              What is it? Describe it in your own words.
            </label>
            <textarea
              id="notes"
              name="notes"
              rows={4}
              maxLength={2000}
              autoFocus
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="bg-background w-full rounded-xl border-0 p-4"
              placeholder="পাটের পাটি, ফরিদপুরে বোনা। নীল ডোরা। প্রায় দুই সপ্তাহ লেগেছে।"
            />
          </div>
        )}
      </div>

      <div className="flex justify-center">
        <DraftButton disabled={nothingYet} />
      </div>

      {state.error && (
        <Alert variant="destructive" className="rounded-2xl">
          <AlertCircle className="size-4" />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      {state.draft && (
        <div className="bg-background/70 mx-auto max-w-md space-y-1 rounded-2xl p-4 text-sm">
          <p className="font-semibold">Filled in below — have a look.</p>
          {state.draft.heard && (
            // What it heard, in her own language. If this is wrong, nothing
            // below it is worth reading.
            <p className="opacity-80">
              <span className="font-medium">Heard:</span> “{state.draft.heard}”
            </p>
          )}
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
