"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Mic, Square, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";

// A voice note, not a podcast. Long enough to describe a piece properly,
// short enough that a forgotten recording cannot run into a bill.
const MAX_SECONDS = 120;

// In preference order. Chrome records webm, Safari mp4, Firefox ogg; all three
// are containers the model accepts, so whichever the browser offers is sent as
// it was recorded.
const FORMATS = [
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
  "audio/mp4",
  "audio/webm",
];

function supportedFormat(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return FORMATS.find((type) => MediaRecorder.isTypeSupported(type));
}

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * Recording the artisan describing the piece.
 *
 * The recording is handed to the form through a hidden file input rather than
 * component state: a server action submits a form, and a Blob that is not in
 * the form is a Blob that never gets sent.
 */
export function VoiceNote({
  name = "voice",
  onRecorded,
}: {
  name?: string;
  /** Told when a clip appears or is thrown away, so the form can enable its button. */
  onRecorded?: (has: boolean) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [clip, setClip] = useState<string>();
  const [error, setError] = useState<string>();

  const inputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder>(null);

  // Whether this browser can record at all. Read through an external store
  // rather than set in an effect: the answer differs between the server (no
  // MediaRecorder, and no microphone to offer) and the browser, and this is
  // how React is told that on purpose instead of by a hydration mismatch.
  const canRecord = useSyncExternalStore(
    () => () => {},
    () => supportedFormat() !== undefined,
    () => false,
  );

  useEffect(() => {
    if (!recording) return;
    const tick = setInterval(() => setSeconds((s) => s + 1), 1000);
    // The cap is a timer of its own rather than a reaction to the count: a
    // recording that runs past it stops because time passed, not because a
    // render noticed.
    const limit = setTimeout(
      () => recorderRef.current?.stop(),
      MAX_SECONDS * 1000,
    );
    return () => {
      clearInterval(tick);
      clearTimeout(limit);
    };
  }, [recording]);

  // A recording left behind is a microphone light left on.
  useEffect(() => {
    return () => {
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
      setClip((old) => {
        if (old) URL.revokeObjectURL(old);
        return undefined;
      });
    };
  }, []);

  async function start() {
    setError(undefined);
    const format = supportedFormat();
    if (!format) return;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      // Refused, or no microphone. Either way she can still type.
      setError("Poshra could not use the microphone. You can type instead.");
      return;
    }

    const recorder = new MediaRecorder(stream, { mimeType: format });
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      setRecording(false);
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks, { type: format });
      const extension = format.includes("ogg")
        ? "ogg"
        : format.includes("mp4")
          ? "m4a"
          : "webm";
      // Into the form, as a file the action can forward untouched.
      const transfer = new DataTransfer();
      transfer.items.add(
        new File([blob], `voice.${extension}`, { type: format }),
      );
      if (inputRef.current) inputRef.current.files = transfer.files;
      setClip((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(blob);
      });
      onRecorded?.(true);
    };

    recorderRef.current = recorder;
    setSeconds(0);
    setClip(undefined);
    recorder.start();
    setRecording(true);
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  function discard() {
    onRecorded?.(false);
    if (inputRef.current) inputRef.current.value = "";
    setClip((old) => {
      if (old) URL.revokeObjectURL(old);
      return undefined;
    });
    setSeconds(0);
  }

  if (!canRecord) {
    // No MediaRecorder: an older browser, or a page served without TLS. The
    // field simply is not there, rather than being there and doing nothing.
    return null;
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        name={name}
        accept="audio/*"
        className="sr-only"
      />

      {clip ? (
        <div className="flex flex-wrap items-center gap-3">
          <audio controls src={clip} className="h-9 max-w-full" />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="rounded-full"
            onClick={discard}
          >
            <Trash2 className="size-4" aria-hidden />
            Record again
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant={recording ? "destructive" : "secondary"}
            size="sm"
            className="rounded-full"
            onClick={recording ? stop : start}
          >
            {recording ? (
              <>
                <Square className="size-3.5" aria-hidden />
                Stop
              </>
            ) : (
              <>
                <Mic className="size-4" aria-hidden />
                Say it instead
              </>
            )}
          </Button>
          {recording && (
            <p aria-live="polite" className="text-sm font-medium tabular-nums">
              <span className="text-ink-rose">●</span> {clock(seconds)} /{" "}
              {clock(MAX_SECONDS)}
            </p>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="text-ink-rose text-xs font-medium">
          {error}
        </p>
      )}
    </div>
  );
}
