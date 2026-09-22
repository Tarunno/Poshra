import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type Tone = "saffron" | "lilac" | "mint" | "rose" | "sky" | "peach";

const tone = {
  saffron: { surface: "bg-tint-saffron", ink: "text-ink-saffron" },
  lilac: { surface: "bg-tint-lilac", ink: "text-ink-lilac" },
  mint: { surface: "bg-tint-mint", ink: "text-ink-mint" },
  rose: { surface: "bg-tint-rose", ink: "text-ink-rose" },
  sky: { surface: "bg-tint-sky", ink: "text-ink-sky" },
  peach: { surface: "bg-tint-peach", ink: "text-ink-peach" },
} satisfies Record<Tone, { surface: string; ink: string }>;

type Props = {
  eyebrow: string;
  icon: LucideIcon;
  title: string;
  body?: string;
  href?: string;
  cta?: string;
  color?: Tone;
  className?: string;
  children?: React.ReactNode;
};

/**
 * The page's building block: a soft pastel panel.
 *
 * Colour lives in the surface and the small eyebrow chip, never in the
 * heading, so body copy keeps full contrast against the tint.
 */
export function TintedCard({
  eyebrow,
  icon: Icon,
  title,
  body,
  href,
  cta,
  color = "saffron",
  className,
  children,
}: Props) {
  const { surface, ink } = tone[color];

  return (
    <section
      className={cn(
        surface,
        "rounded-panel stitched group relative p-7 transition-transform duration-200 hover:-translate-y-1 sm:p-9",
        className,
      )}
    >
      <p
        className={cn(
          ink,
          "bg-background/70 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide uppercase",
        )}
      >
        <Icon className="size-3.5" aria-hidden />
        {eyebrow}
      </p>
      <h2 className="mt-5 text-2xl leading-[1.15] font-bold tracking-tight text-balance sm:text-[1.75rem]">
        {title}
      </h2>
      {body && (
        <p className="mt-3 max-w-prose text-[0.95rem] leading-relaxed opacity-80">
          {body}
        </p>
      )}
      {href && (
        <Link
          href={href}
          className="mt-6 inline-flex items-center gap-1 text-sm font-semibold underline-offset-4 hover:underline"
        >
          {cta ?? "Learn more"}
          <ArrowUpRight className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
        </Link>
      )}
      {children}
    </section>
  );
}
