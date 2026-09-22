/**
 * A kantha patchwork square.
 *
 * Nakshi kantha is made by layering worn cloth and quilting it with a running
 * stitch, so the art is literally patches joined by stitches. Each patch
 * carries a different traditional motif: the jamdani diamond, a lotus, a fish
 * (the delta's staple), a paisley, and the running stitch itself.
 */
export function CraftPatch({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 300 300"
      className={className}
      role="img"
      aria-label="A kantha patchwork square stitched from traditional Bengali motifs."
    >
      <defs>
        <pattern
          id="patch-stitch"
          width="14"
          height="14"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M0 7 H14"
            fill="none"
            stroke="var(--app-fg)"
            strokeWidth="1.4"
            strokeDasharray="5 5"
            opacity="0.25"
          />
        </pattern>
      </defs>

      <g
        stroke="var(--app-fg)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {/* patches */}
        <rect
          x="8"
          y="8"
          width="136"
          height="136"
          rx="14"
          fill="var(--tint-saffron)"
        />
        <rect
          x="156"
          y="8"
          width="136"
          height="90"
          rx="14"
          fill="var(--tint-lilac)"
        />
        <rect
          x="156"
          y="110"
          width="136"
          height="90"
          rx="14"
          fill="var(--tint-mint)"
        />
        <rect
          x="8"
          y="156"
          width="90"
          height="136"
          rx="14"
          fill="var(--tint-rose)"
        />
        <rect
          x="110"
          y="156"
          width="80"
          height="136"
          rx="14"
          fill="var(--tint-sky)"
        />
        <rect
          x="202"
          y="212"
          width="90"
          height="80"
          rx="14"
          fill="var(--tint-peach)"
        />

        {/* quilting: the running stitch that holds the layers together */}
        <g stroke="none" fill="url(#patch-stitch)">
          <rect x="8" y="8" width="136" height="136" rx="14" />
          <rect x="110" y="156" width="80" height="136" rx="14" />
        </g>

        {/* jamdani diamonds */}
        <g transform="translate(76 76)" fill="none" strokeWidth="2">
          {[0, 1, 2].map((ring) => (
            <path
              key={ring}
              d={`M0 ${-16 - ring * 16} L${16 + ring * 16} 0 L0 ${16 + ring * 16} L${-16 - ring * 16} 0 Z`}
              opacity={0.85 - ring * 0.2}
            />
          ))}
          <circle r="4" fill="var(--ink-saffron)" stroke="none" />
        </g>

        {/* lotus */}
        <g transform="translate(224 53)" fill="var(--tint-saffron)">
          {[-50, -25, 0, 25, 50].map((angle) => (
            <ellipse
              key={angle}
              rx="9"
              ry="22"
              transform={`rotate(${angle}) translate(0 -16)`}
            />
          ))}
          <path d="M-34 14 Q0 30 34 14" fill="none" strokeWidth="2" />
        </g>

        {/* fish: the river's staple, a recurring kantha motif */}
        <g transform="translate(224 155)">
          <path
            d="M-34 0 C-18 -20 18 -20 30 0 C18 20 -18 20 -34 0 Z"
            fill="var(--tint-sky)"
          />
          <path d="M30 0 L46 -12 L46 12 Z" fill="var(--tint-sky)" />
          <circle cx="-16" cy="-4" r="2.6" fill="var(--app-fg)" stroke="none" />
          <path
            d="M-6 -10 q8 10 0 20"
            fill="none"
            strokeWidth="1.8"
            opacity="0.6"
          />
          <path
            d="M6 -8 q8 8 0 16"
            fill="none"
            strokeWidth="1.8"
            opacity="0.6"
          />
        </g>

        {/* paisley */}
        <g transform="translate(53 224)" fill="var(--tint-peach)">
          <path d="M-14 34 C-34 10 -18 -22 6 -30 C28 -36 34 -8 18 6 C6 16 12 26 20 30 C6 38 -4 42 -14 34 Z" />
          <path
            d="M-6 20 C-16 6 -8 -12 6 -18"
            fill="none"
            strokeWidth="1.8"
            strokeDasharray="4 4"
            opacity="0.7"
          />
        </g>

        {/* terracotta pot */}
        <g transform="translate(247 252)">
          <ellipse cx="0" cy="8" rx="26" ry="22" fill="var(--tint-rose)" />
          <ellipse cx="0" cy="-16" rx="11" ry="4" fill="var(--tint-saffron)" />
          <path d="M-9 -14 L9 -14 L7 -6 L-7 -6 Z" fill="var(--tint-rose)" />
          <path
            d="M-20 4 Q0 16 20 4"
            fill="none"
            strokeWidth="1.8"
            strokeDasharray="4 5"
            opacity="0.6"
          />
        </g>

        {/* a kantha stitch sampler: the running stitch itself, as a motif */}
        <g
          transform="translate(150 224)"
          fill="none"
          strokeWidth="2.2"
          opacity="0.75"
        >
          <path d="M-22 -28 H22" strokeDasharray="7 6" />
          <path d="M-22 -10 H22" strokeDasharray="7 6" />
          <path d="M-22 8 H22" strokeDasharray="7 6" />
          <path d="M-22 26 H22" strokeDasharray="7 6" />
          <path d="M-8 -20 L0 -12 M0 -20 L-8 -12" />
          <path d="M6 16 L14 24 M14 16 L6 24" />
        </g>
      </g>
    </svg>
  );
}
