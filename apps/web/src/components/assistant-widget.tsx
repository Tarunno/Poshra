"use client";

import { useEffect, useRef, useState } from "react";
import { MessageCircleOff, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ShoppingChat } from "@/components/shopping-chat";

/**
 * The assistant, available from wherever the shopper already is.
 *
 * Collapsing hides the panel rather than unmounting it, so a conversation
 * survives being put away — closing it mid-answer and losing everything is the
 * quickest way to make people stop using it. The cost is that the chat stays
 * mounted on every page, which is a few kilobytes of state and no requests.
 */
export function AssistantWidget() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Escape closes it, the way every other dialog on the web does.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  return (
    <>
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-label="Ask Poshra"
        // Hidden, not removed: the conversation is in this subtree.
        aria-hidden={!open}
        className={`bg-background fixed z-50 flex flex-col rounded-3xl shadow-2xl transition-all duration-200 outline-none ${
          open
            ? "pointer-events-auto scale-100 opacity-100"
            : "pointer-events-none scale-95 opacity-0"
        } inset-x-3 bottom-3 top-20 sm:inset-x-auto sm:top-auto sm:right-5 sm:bottom-24 sm:h-[34rem] sm:w-[25rem]`}
      >
        <header className="bg-tint-saffron/70 flex items-center justify-between gap-2 rounded-t-3xl px-5 py-3.5">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="size-4" aria-hidden />
            Ask Poshra
          </p>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 rounded-full"
            onClick={() => setOpen(false)}
            aria-label="Close the assistant"
          >
            <X className="size-4" aria-hidden />
          </Button>
        </header>

        {/* The only scrolling region, so the composer stays put. */}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <ShoppingChat compact />
        </div>
      </div>

      <Button
        size="icon"
        onClick={() => setOpen((was) => !was)}
        aria-expanded={open}
        aria-label={open ? "Hide the assistant" : "Ask Poshra"}
        className="fixed right-5 bottom-5 z-50 size-14 rounded-full shadow-lg transition hover:scale-105"
      >
        {open ? (
          <MessageCircleOff className="size-5" aria-hidden />
        ) : (
          <Sparkles className="size-5" aria-hidden />
        )}
      </Button>
    </>
  );
}
