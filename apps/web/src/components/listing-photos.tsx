"use client";

import Image from "next/image";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { AlertCircle, ImagePlus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PhotoDropzone } from "@/components/photo-dropzone";
import {
  deleteImageAction,
  uploadImageAction,
  type ImageState,
} from "@/lib/image-actions";
import type { ProductImage } from "@/lib/catalog";

function UploadButton() {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="lg"
      className="rounded-full px-6"
      disabled={pending}
    >
      <ImagePlus className="size-4" aria-hidden />
      {pending ? "Uploading…" : "Add photograph"}
    </Button>
  );
}

/**
 * The photographs on a listing.
 *
 * One form, not several. The drop target sits in the same grid as the
 * photographs so adding one reads as filling the next tile, and HTML forbids
 * nesting a form inside a form — so removing a photograph is a submit button
 * with its own formAction rather than a form of its own. It skips validation,
 * because the file input is required for adding and irrelevant to removing.
 *
 * Upload is separate from the listing form on purpose: a photograph is saved
 * the moment it is chosen, so nobody loses one by leaving without saving.
 */
export function ListingPhotos({
  slug,
  images,
  max,
}: {
  slug: string;
  images: ProductImage[];
  max: number;
}) {
  const [state, formAction] = useActionState(
    uploadImageAction,
    {} as ImageState,
  );
  const full = images.length >= max;

  return (
    <form action={formAction} className="space-y-5">
      <input type="hidden" name="slug" value={slug} />

      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
          Photographs
        </h2>
        <p className="text-xs opacity-60">
          {images.length} of {max}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
        {images.map((image, index) => (
          <div key={image.id} className="relative">
            <div className="relative aspect-square overflow-hidden rounded-2xl">
              <Image
                src={image.url}
                alt={image.alt_text || `Photograph ${index + 1}`}
                fill
                sizes="(min-width: 640px) 20vw, 30vw"
                className="object-cover"
              />
            </div>
            {index === 0 && (
              <span className="bg-background/85 absolute top-2 left-2 rounded-full px-2 py-0.5 text-[0.65rem] font-semibold backdrop-blur">
                Cover
              </span>
            )}
            <Button
              type="submit"
              formAction={deleteImageAction}
              // The file input is required for adding and meaningless here.
              formNoValidate
              name="image_id"
              value={String(image.id)}
              variant="ghost"
              size="icon"
              className="bg-background/85 text-ink-rose absolute top-2 right-2 size-7 rounded-full backdrop-blur"
              aria-label={`Remove photograph ${index + 1}`}
            >
              <Trash2 className="size-3.5" aria-hidden />
            </Button>
          </div>
        ))}

        {!full && <PhotoDropzone name="file" />}
      </div>

      {full ? (
        <p className="text-sm opacity-70">
          That is the most a listing can hold. Remove one to add another.
        </p>
      ) : (
        <>
          <p className="text-xs opacity-60">
            JPEG, PNG or WebP, up to 6 MB. Location data is removed when it is
            stored.
          </p>

          <div className="space-y-2">
            <Label htmlFor="alt_text">Describe it (for screen readers)</Label>
            <Input
              id="alt_text"
              name="alt_text"
              maxLength={200}
              placeholder="A folded indigo kantha with a lotus at its centre"
              className="bg-background h-11 rounded-xl border-0 px-4"
            />
          </div>

          {state.error && (
            <p
              role="alert"
              className="text-ink-rose flex items-center gap-1.5 text-sm font-medium"
            >
              <AlertCircle className="size-4" aria-hidden />
              {state.error}
            </p>
          )}

          <UploadButton />
        </>
      )}
    </form>
  );
}
