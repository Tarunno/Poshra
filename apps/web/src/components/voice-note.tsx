"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Mic, Square, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";

// A voice note, not a podcast. Long enough to describe a piece properly,
// short enough that a forgotten recording cannot run into a bill.
const MAX_SECONDS = 120;
const BARS = 21;

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
 * The artisan describing her own work, out loud.
 *
 * The microphone is the largest thing on the page because speaking is the
 * point: a weaver who would never fill in eight fields in English will say
 * what a piece is in a sentence. Typing is still there, underneath, for when
 * she would rather.
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
  const barsRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<AudioContext>(null);
  const frameRef = useRef<number>(null);

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
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      audioRef.current?.close();
      setClip((old) => {
        if (old) URL.revokeObjectURL(old);
        return undefined;
      });
    };
  }, []);

  /**
   * The bars, driven straight from the microphone.
   *
   * Heights are written to the DOM rather than held in state: this runs sixty
   * times a second, and re-rendering the page that often to move a few pixels
   * is how an interface starts dropping what somebody is typing.
   */
  function listen(stream: MediaStream) {
    const context = new AudioContext();
    const analyser = context.createAnalyser();
    analyser.fftSize = 64;
    analyser.smoothingTimeConstant = 0.75;
    context.createMediaStreamSource(stream).connect(analyser);
    audioRef.current = context;

    const levels = new Uint8Array(analyser.frequencyBinCount);
    const draw = () => {
      analyser.getByteFrequencyData(levels);
      const children = barsRef.current?.children;
      if (children) {
        for (let index = 0; index < children.length; index++) {
          // Reading outwards from the middle, so the loudest part of a voice
          // sits at the centre of the row rather than at one end.
          const distance = Math.abs(index - (BARS - 1) / 2);
          const level = levels[Math.round(distance) + 1] ?? 0;
          const height = 3 + (level / 255) * 25;
          (children[index] as HTMLElement).style.height = `${height}px`;
        }
      }
      frameRef.current = requestAnimationFrame(draw);
    };
    draw();
  }

  function quieten() {
    if (frameRef.current) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    audioRef.current?.close();
    audioRef.current = null;
    const children = barsRef.current?.children;
    if (children) {
      for (let index = 0; index < children.length; index++) {
        (children[index] as HTMLElement).style.height = "3px";
      }
    }
  }

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
      quieten();
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
    listen(stream);
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

  return (
    <div className="flex flex-col items-center gap-3">
      <input
        ref={inputRef}
        type="file"
        name={name}
        accept="audio/*"
        className="sr-only"
      />

      {clip ? (
        <div className="flex flex-col items-center gap-3">
          <audio controls src={clip} className="h-10 max-w-full" />
          <p className="text-sm font-medium opacity-70">
            {clock(seconds)} recorded — have a listen, then draft it.
          </p>
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
        <>
          <div className="relative flex size-36 items-center justify-center">
            {/* The patch under it, breathing while it listens. */}
            {recording && (
              <span
                aria-hidden
                className="bg-tint-rose patch-breathing absolute inset-1 rounded-full"
              />
            )}
            {/* A running stitch around the whole thing, turning. */}
            <svg
              aria-hidden
              viewBox="0 0 100 100"
              className={`absolute inset-0 size-full ${recording ? "stitch-turning" : ""}`}
            >
              <circle
                cx="50"
                cy="50"
                r="46"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeDasharray="5 7"
                className={recording ? "text-ink-rose" : "opacity-35"}
              />
            </svg>

            <button
              type="button"
              onClick={recording ? () => recorderRef.current?.stop() : start}
              disabled={!canRecord}
              aria-label={recording ? "Stop recording" : "Record a description"}
              className="bg-foreground text-background focus-visible:ring-foreground/40 relative flex size-24 items-center justify-center rounded-full transition-transform hover:scale-[1.04] focus-visible:ring-2 focus-visible:ring-offset-4 focus-visible:outline-none disabled:opacity-40"
            >
              {recording ? (
                <Square className="size-7 fill-current" aria-hidden />
              ) : (
                <Mic className="size-9" aria-hidden />
              )}
            </button>
          </div>

          {/* The bars only mean anything while something is being said. */}
          <div
            ref={barsRef}
            aria-hidden
            className={`flex h-7 items-center gap-[3px] transition-opacity ${
              recording ? "opacity-100" : "opacity-0"
            }`}
          >
            {Array.from({ length: BARS }, (_, index) => (
              <span
                key={index}
                className="bg-ink-rose/70 w-[3px] rounded-full"
                style={{ height: 3 }}
              />
            ))}
          </div>

          <p aria-live="polite" className="text-sm font-medium">
            {!canRecord ? (
              <span className="opacity-60">
                This browser cannot record — type a few words instead.
              </span>
            ) : recording ? (
              <>
                <span className="text-ink-rose">Poshra is listening</span>
                <span className="ml-2 tabular-nums opacity-60">
                  {clock(seconds)} / {clock(MAX_SECONDS)}
                </span>
              </>
            ) : (
              <span className="opacity-70">
                Tap and tell Poshra what you made, in Bangla
              </span>
            )}
          </p>
        </>
      )}

      {error && (
        <p role="alert" className="text-ink-rose text-xs font-medium">
          {error}
        </p>
      )}
    </div>
  );
}
