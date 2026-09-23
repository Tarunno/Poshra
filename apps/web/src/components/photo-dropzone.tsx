"use client";

import { useRef, useState } from "react";
import { ImagePlus, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";

const ACCEPT = "image/jpeg,image/png,image/webp";

/**
 * A drop target that is really a file input.
 *
 * The input stays the control: it keeps the keyboard and the screen-reader
 * behaviour, and the form still submits if the drop handlers never run. The
 * dragging only writes into that input, so nothing here is the only way to
 * add a photograph.
 */
export function PhotoDropzone({
  name,
  disabled,
}: {
  name: string;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [chosen, setChosen] = useState<string>();

  function accept(files: FileList | null) {
    const file = files?.[0];
    if (!file || !inputRef.current) return;
    // A DataTransfer is the only way to put a dropped file into an input, so
    // the form submits it exactly as if it had been picked.
    const transfer = new DataTransfer();
    transfer.items.add(file);
    inputRef.current.files = transfer.files;
    setChosen(file.name);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        if (!disabled) accept(event.dataTransfer.files);
      }}
      className={`rounded-2xl border-2 border-dashed p-6 text-center transition ${
        over
          ? "border-foreground/40 bg-background"
          : "border-foreground/15 bg-background/50"
      } ${disabled ? "opacity-50" : ""}`}
    >
      <input
        ref={inputRef}
        id={name}
        name={name}
        type="file"
        accept={ACCEPT}
        required
        disabled={disabled}
        onChange={(event) => setChosen(event.target.files?.[0]?.name)}
        // Visually hidden rather than display:none, so it stays focusable and
        // the browser still reports a missing file on submit.
        className="sr-only"
      />

      {chosen ? (
        <p className="flex items-center justify-center gap-2 text-sm font-semibold">
          <ImagePlus className="size-4" aria-hidden />
          {chosen}
        </p>
      ) : (
        <p className="flex items-center justify-center gap-2 text-sm opacity-70">
          <Upload className="size-4" aria-hidden />
          Drop a photograph here
        </p>
      )}

      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="mt-3 rounded-full"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        {chosen ? "Choose a different one" : "Or choose a file"}
      </Button>
    </div>
  );
}
