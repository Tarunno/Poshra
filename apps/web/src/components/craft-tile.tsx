/**
 * Stand-in artwork for a product that has no photograph yet.
 *
 * Each craft gets its own motif and tint, chosen from the craft slug, so a
 * grid of listings looks deliberate rather than broken, and two jamdani pieces
 * never look identical: a seed drawn from the product slug shifts the pattern.
 *
 * Replaced by the real photograph as soon as listings carry images.
 */
import { cn } from "@/lib/utils";

type Tone = "saffron" | "lilac" | "mint" | "rose" | "sky" | "peach";

const CRAFT_STYLE: Record<string, Tone> = {
  jamdani: "rose",
  "nakshi-kantha": "saffron",
  terracotta: "peach",
  jute: "mint",
  shitalpati: "sky",
  brass: "lilac",
};

const SURFACE: Record<Tone, string> = {
  saffron: "bg-tint-saffron",
  lilac: "bg-tint-lilac",
  mint: "bg-tint-mint",
  rose: "bg-tint-rose",
  sky: "bg-tint-sky",
  peach: "bg-tint-peach",
};

/** Small deterministic hash, so the same product always draws the same motif. */
function seedOf(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1)
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  return hash;
}

function Motif({ craft, seed }: { craft: string; seed: number }) {
  const stroke = {
    fill: "none",
    stroke: "var(--app-fg)",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    opacity: 0.55,
  };

  switch (craft) {
    case "jamdani":
      // The woven lattice, offset by the seed so pieces differ.
      return (
        <g {...stroke}>
          {Array.from({ length: 4 }).map((_, row) =>
            Array.from({ length: 4 }).map((__, col) => {
              const x = 30 + col * 40 + ((seed >> (row + col)) % 6);
              const y = 30 + row * 40;
              return (
                <path
                  key={`${row}-${col}`}
                  d={`M${x} ${y - 11} L${x + 11} ${y} L${x} ${y + 11} L${x - 11} ${y} Z`}
                />
              );
            }),
          )}
        </g>
      );
    case "nakshi-kantha":
      // Rows of running stitch with knots, the way a kantha is quilted.
      return (
        <g {...stroke}>
          {Array.from({ length: 6 }).map((_, row) => (
            <path
              key={row}
              d={`M18 ${26 + row * 30} H182`}
              strokeDasharray={`${8 + ((seed >> row) % 5)} 7`}
            />
          ))}
          <path d="M88 96 L112 120 M112 96 L88 120" />
        </g>
      );
    case "terracotta":
      return (
        <g {...stroke}>
          <ellipse cx="100" cy="126" rx="52" ry="44" />
          <path d="M84 70 L116 70 L110 86 L90 86 Z" />
          <ellipse cx="100" cy="68" rx="22" ry="7" />
          <path d="M56 116 Q100 136 144 116" strokeDasharray="7 7" />
          <path d="M64 144 Q100 158 136 144" />
        </g>
      );
    case "jute":
      // Plain weave: warp over weft.
      return (
        <g {...stroke}>
          {Array.from({ length: 5 }).map((_, i) => (
            <path key={`h${i}`} d={`M24 ${40 + i * 30} H176`} />
          ))}
          {Array.from({ length: 5 }).map((_, i) => (
            <path
              key={`v${i}`}
              d={`M${40 + i * 30} 24 V176`}
              strokeDasharray="14 14"
            />
          ))}
        </g>
      );
    case "shitalpati":
      // Fine cane strips crossing on the diagonal.
      return (
        <g {...stroke}>
          {Array.from({ length: 7 }).map((_, i) => (
            <path key={`a${i}`} d={`M${-20 + i * 36} 180 L${60 + i * 36} 20`} />
          ))}
          {Array.from({ length: 7 }).map((_, i) => (
            <path
              key={`b${i}`}
              d={`M${-20 + i * 36} 20 L${60 + i * 36} 180`}
              strokeDasharray="10 10"
            />
          ))}
        </g>
      );
    case "brass":
      return (
        <g {...stroke}>
          <ellipse cx="100" cy="150" rx="46" ry="12" />
          <path d="M100 138 V96" />
          <path d="M72 60 h56 l-9 20 c20 10 22 40 -19 42 c-41 -2 -39 -32 -19 -42 Z" />
          <path d="M60 46 q12 -14 24 0 M116 46 q12 -14 24 0" />
        </g>
      );
    default:
      return (
        <g {...stroke}>
          <circle cx="100" cy="100" r="46" />
          <circle cx="100" cy="100" r="26" strokeDasharray="8 7" />
        </g>
      );
  }
}

export function CraftTile({
  craftSlug,
  seedKey,
  className,
}: {
  craftSlug: string;
  seedKey: string;
  className?: string;
}) {
  const tone = CRAFT_STYLE[craftSlug] ?? "saffron";
  return (
    <div
      className={cn(SURFACE[tone], "overflow-hidden", className)}
      aria-hidden
    >
      <svg viewBox="0 0 200 200" className="size-full">
        <Motif craft={craftSlug} seed={seedOf(seedKey)} />
      </svg>
    </div>
  );
}
