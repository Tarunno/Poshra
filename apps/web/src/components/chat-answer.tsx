"use client";

import Markdown from "react-markdown";

/**
 * An assistant answer, rendered as the markdown it actually is.
 *
 * The model writes lists and bold titles because that is how it describes
 * several pieces at once. Printed as plain text it came out as literal
 * asterisks, which read like a bug in the shop rather than a formatted answer.
 *
 * Only the elements the model uses are given styles, and no raw HTML is
 * enabled: the text comes from a model that has read product descriptions
 * written by other people, so it is never trusted enough to be markup.
 */
export function ChatAnswer({ children }: { children: string }) {
  return (
    <div className="max-w-2xl space-y-3 text-[0.95rem] leading-relaxed">
      <Markdown
        components={{
          p: ({ children }) => <p>{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="list-disc space-y-1.5 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1.5 pl-5">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-0.5">{children}</li>,
          h1: ({ children }) => <p className="font-semibold">{children}</p>,
          h2: ({ children }) => <p className="font-semibold">{children}</p>,
          h3: ({ children }) => <p className="font-semibold">{children}</p>,
          code: ({ children }) => (
            <code className="bg-muted rounded px-1 py-0.5 text-[0.85em]">
              {children}
            </code>
          ),
          // The assistant links to nothing: products arrive as cards beside the
          // text. Anything that looks like a link is shown as its own words.
          a: ({ children }) => <span>{children}</span>,
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}
