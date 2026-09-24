"use client";

import Link from "next/link";
import { useActionState, useCallback, useState } from "react";
import { useFormStatus } from "react-dom";
import { AlertCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ListingDrafter } from "@/components/listing-drafter";
import type { Craft, Product } from "@/lib/catalog";
import type { ListingDraft } from "@/lib/draft-actions";
import { saveListingAction, type ListingState } from "@/lib/listing-actions";
import { toMajorUnits } from "@/lib/money-input";

const field = "bg-background rounded-xl border-0 h-11 px-4 w-full";
const CURRENCIES = ["BDT", "USD", "EUR", "GBP"];

function SubmitButton({ editing }: { editing: boolean }) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="lg"
      className="rounded-full px-7"
      disabled={pending}
    >
      {pending ? "Saving…" : editing ? "Save changes" : "Create the listing"}
    </Button>
  );
}

/** A field's error from the API, shown under the input it belongs to. */
function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-ink-rose text-xs font-medium">
      {message}
    </p>
  );
}

/**
 * One form for creating and editing.
 *
 * The two differ only in whether a slug travels with the submission, so they
 * share a component rather than drifting apart as two that must be kept in
 * step. Validation errors come back per field from the API, which is the only
 * place that can decide them.
 */
export function ListingForm({
  crafts,
  product,
  drafting = false,
}: {
  crafts: Craft[];
  product?: Product;
  /** Offer to draft the listing from a photograph. New listings only. */
  drafting?: boolean;
}) {
  const [state, formAction] = useActionState(
    saveListingAction,
    {} as ListingState,
  );
  const [draft, setDraft] = useState<ListingDraft>();
  // Bumped when a draft arrives so the fields remount and pick up their new
  // defaults. The inputs are uncontrolled on purpose — the artisan's typing
  // belongs to the browser, not to React state — and a remount is how an
  // uncontrolled field is given a new starting value without stealing it.
  const [filled, setFilled] = useState(0);
  const editing = product !== undefined;
  const errors = state.errors ?? {};

  // Stable, so handing a draft over does not re-run on every render of a form
  // the artisan may be halfway through typing into.
  const fill = useCallback((drafted: ListingDraft) => {
    setDraft(drafted);
    setFilled((count) => count + 1);
  }, []);

  return (
    <>
      {drafting && (
        <div className="bg-tint-sky rounded-panel stitched mb-6 p-6 sm:p-8">
          <ListingDrafter onDrafted={fill} />
        </div>
      )}

      <form
        action={formAction}
        className={
          drafting
            ? "bg-tint-lilac rounded-panel stitched space-y-6 p-6 sm:p-8"
            : "space-y-6"
        }
        key={filled}
      >
        {editing && <input type="hidden" name="slug" value={product.slug} />}

        {state.message && (
          <Alert variant="destructive" className="rounded-2xl">
            <AlertCircle className="size-4" />
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-2">
          <Label htmlFor="title">What is it?</Label>
          <Input
            className={field}
            id="title"
            name="title"
            required
            maxLength={140}
            defaultValue={product?.title ?? draft?.title}
            placeholder="Nakshi kantha, lotus and fish"
          />
          <FieldError message={errors.title} />
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="craft">Craft</Label>
            <select
              id="craft"
              name="craft"
              required
              defaultValue={product?.craft.slug ?? draft?.craft}
              className={field}
            >
              <option value="">Choose a craft…</option>
              {crafts.map((craft) => (
                <option key={craft.slug} value={craft.slug}>
                  {craft.name}
                </option>
              ))}
            </select>
            <FieldError message={errors.craft} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="origin_district">Made in</Label>
            <Input
              className={field}
              id="origin_district"
              name="origin_district"
              maxLength={60}
              defaultValue={product?.origin_district}
              placeholder="Jamalpur"
            />
            <FieldError message={errors.origin_district} />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Its story</Label>
          <textarea
            id="description"
            name="description"
            rows={5}
            defaultValue={product?.description ?? draft?.description}
            className="bg-background w-full rounded-xl border-0 p-4"
            placeholder="How it is made, how long it took, what the motifs mean."
          />
          <FieldError message={errors.description} />
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="materials">Materials</Label>
            <Input
              className={field}
              id="materials"
              name="materials"
              maxLength={200}
              defaultValue={product?.materials ?? draft?.materials}
              placeholder="Recycled cotton, silk thread"
            />
            <FieldError message={errors.materials} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="dimensions">Size</Label>
            <Input
              className={field}
              id="dimensions"
              name="dimensions"
              maxLength={120}
              defaultValue={product?.dimensions ?? draft?.dimensions}
              placeholder="190 × 140 cm"
            />
            <FieldError message={errors.dimensions} />
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="price">Price</Label>
            <Input
              className={field}
              id="price"
              name="price"
              required
              inputMode="decimal"
              defaultValue={
                product
                  ? toMajorUnits(product.price_minor, product.currency)
                  : draft?.suggested_price_minor
                    ? toMajorUnits(draft.suggested_price_minor, "BDT")
                    : ""
              }
              placeholder="5600"
            />
            {/* The field takes taka; the API stores paisa. The conversion is the
              server's job, so a typo cannot become a hundredfold price. */}
            <FieldError message={errors.price ?? errors.price_minor} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="currency">Currency</Label>
            <select
              id="currency"
              name="currency"
              defaultValue={product?.currency ?? "BDT"}
              className={field}
            >
              {CURRENCIES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <FieldError message={errors.currency} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="stock">How many exist</Label>
            <Input
              className={field}
              id="stock"
              name="stock"
              type="number"
              min={0}
              required
              defaultValue={product?.stock ?? 1}
            />
            <FieldError message={errors.stock} />
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="lead_time_days">Days to make and send</Label>
            <Input
              className={field}
              id="lead_time_days"
              name="lead_time_days"
              type="number"
              min={0}
              max={365}
              required
              defaultValue={product?.lead_time_days ?? 7}
            />
            <FieldError message={errors.lead_time_days} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="status">Visibility</Label>
            <select
              id="status"
              name="status"
              defaultValue={product?.status ?? "draft"}
              className={field}
            >
              <option value="draft">Draft — only you can see it</option>
              <option value="published">Published — in the shop</option>
              <option value="archived">Archived — hidden, kept</option>
            </select>
            <FieldError message={errors.status} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 pt-2">
          <SubmitButton editing={editing} />
          <Link
            href="/dashboard/listings"
            className="text-sm font-semibold underline-offset-4 hover:underline"
          >
            Cancel
          </Link>
        </div>
      </form>
    </>
  );
}
