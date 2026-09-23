"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { ImagePlus, Upload } from "lucide-react";

const ACCEPT = "image/jpeg,image/png,image/webp";

/**
 * A drop target shaped like the photographs beside it, so adding one reads as
 * filling the next tile rather than using a separate machine.
 *
 * The file input is still the control: dragging only writes into it, so the
 * keyboard, the screen reader and the browser's own "choose a file" validation
 * keep working whether or not anything is ever dropped.
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
  const [preview, setPreview] = useState<{ url: string; name: string }>();

  // An object URL holds the file in memory until it is released.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview.url);
    };
  }, [preview]);

  function accept(files: FileList | null) {
    const file = files?.[0];
    if (!file || !inputRef.current) return;
    // A DataTransfer is the only way to put a dropped file into an input, so
    // the form submits it exactly as if it had been picked.
    const transfer = new DataTransfer();
    transfer.items.add(file);
    inputRef.current.files = transfer.files;
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old.url);
      return { url: URL.createObjectURL(file), name: file.name };
    });
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
      className={`relative aspect-square overflow-hidden rounded-2xl border-2 border-dashed transition ${
        over
          ? "border-foreground/50 bg-background"
          : "border-foreground/20 bg-background/40"
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
        onChange={(event) => accept(event.target.files)}
        // Visually hidden rather than removed, so it stays focusable and the
        // browser still reports a missing file on submit.
        className="sr-only"
      />

      {preview && (
        <Image
          src={preview.url}
          alt=""
          fill
          // A local object URL is not something the optimiser can fetch.
          unoptimized
          className="object-cover opacity-40"
        />
      )}

      <label
        htmlFor={name}
        className="absolute inset-0 flex cursor-pointer flex-col items-center justify-center gap-1.5 p-3 text-center"
      >
        {preview ? (
          <>
            <ImagePlus className="size-5" aria-hidden />
            <span className="line-clamp-2 text-xs font-semibold break-all">
              {preview.name}
            </span>
            <span className="text-[0.7rem] opacity-70">Choose another</span>
          </>
        ) : (
          <>
            <Upload className="size-5 opacity-60" aria-hidden />
            <span className="text-xs font-semibold">Drop a photograph</span>
            <span className="text-[0.7rem] opacity-70">or click to choose</span>
          </>
        )}
      </label>
    </div>
  );
}
