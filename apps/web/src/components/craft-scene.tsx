/**
 * Hero illustration: the Bengal delta and the crafts that come from it.
 *
 * Motifs: a country boat (nouka) whose sail carries the jamdani diamond
 * lattice, terracotta pots from Dhamrai, jute stalks, shapla water lilies (the
 * national flower) and a stack of textiles sewn with nakshi kantha running
 * stitch. The sun is drawn as a rickshaw-art flower.
 *
 * Three bands give the scene depth: sky, river, then land in front, so every
 * object sits on a surface instead of floating.
 *
 * Colours come from the page's pastel tokens, so the art follows the theme
 * rather than carrying its own palette.
 */
export function CraftScene({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 600 420"
      className={className}
      role="img"
      aria-label="A country boat with a jamdani-patterned sail on a river, with terracotta pots, jute stalks, water lilies and a stack of kantha-stitched textiles on the bank."
    >
      <defs>
        {/* Jamdani: a supplementary-weft lattice of small diamonds. */}
        <pattern
          id="jamdani"
          width="20"
          height="20"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M10 3 L17 10 L10 17 L3 10 Z"
            fill="none"
            stroke="var(--ink-rose)"
            strokeWidth="1.1"
            opacity="0.6"
          />
          <circle
            cx="10"
            cy="10"
            r="1.5"
            fill="var(--ink-rose)"
            opacity="0.5"
          />
        </pattern>
        <radialGradient id="sunGlow">
          <stop offset="55%" stopColor="var(--tint-saffron)" />
          <stop offset="100%" stopColor="var(--tint-saffron)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <g
        stroke="var(--app-fg)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {/* ---------------- sky ---------------- */}
        <circle cx="486" cy="86" r="74" fill="url(#sunGlow)" stroke="none" />
        <g transform="translate(486 86)">
          {/* rickshaw-art flower sun */}
          {Array.from({ length: 10 }).map((_, i) => (
            <ellipse
              key={i}
              rx="11"
              ry="26"
              fill="var(--tint-saffron)"
              transform={`rotate(${i * 36}) translate(0 -24)`}
            />
          ))}
          <circle r="19" fill="var(--tint-peach)" />
          <circle r="8" fill="var(--tint-saffron)" />
        </g>
        <g fill="none" strokeWidth="2.2" opacity="0.65">
          <path d="M92 86 q9 -8 18 0 q9 -8 18 0" />
          <path d="M140 58 q7 -6 14 0 q7 -6 14 0" />
          <path d="M196 96 q7 -6 14 0 q7 -6 14 0" />
        </g>

        {/* ---------------- river ---------------- */}
        <path
          d="M0 252 C90 236 160 268 250 256 C340 244 430 272 520 258 C556 252 580 248 600 250
             L600 338 C520 350 460 328 380 338 C300 348 220 328 140 338 C90 344 40 336 0 342 Z"
          fill="var(--tint-sky)"
        />
        <g fill="none" strokeWidth="2" opacity="0.4">
          <path d="M60 286 q18 -10 36 0 t36 0" />
          <path d="M430 290 q18 -10 36 0 t36 0" />
        </g>

        {/* ---------------- boat with a jamdani sail ---------------- */}
        <g>
          <line x1="300" y1="250" x2="300" y2="118" strokeWidth="3" />
          <path d="M300 118 L334 128 L300 138 Z" fill="var(--tint-mint)" />
          {/* sail */}
          <path
            d="M306 130 C374 168 374 214 306 248 Z"
            fill="var(--tint-rose)"
          />
          <path
            d="M306 130 C374 168 374 214 306 248 Z"
            fill="url(#jamdani)"
            stroke="none"
          />
          <path
            d="M294 150 C246 180 246 220 294 246 Z"
            fill="var(--tint-peach)"
          />
          {/* hull: upswept prow and stern, the shape of a river nouka */}
          <path
            d="M176 244 C206 240 250 252 300 252 C350 252 394 240 424 244
               C414 294 368 316 300 316 C232 316 186 294 176 244 Z"
            fill="var(--tint-saffron)"
          />
          <path
            d="M196 264 C244 276 356 276 404 264"
            fill="none"
            strokeWidth="2"
            opacity="0.45"
          />
        </g>

        {/* ---------------- shapla water lilies ---------------- */}
        {[
          { x: 196, y: 296, s: 0.9 },
          { x: 470, y: 310, s: 0.72 },
        ].map(({ x, y, s }) => (
          <g key={x} transform={`translate(${x} ${y}) scale(${s})`}>
            <ellipse cx="30" cy="10" rx="26" ry="9" fill="var(--tint-mint)" />
            <g>
              {[0, 60, 120, 180, 240, 300].map((angle) => (
                <ellipse
                  key={angle}
                  rx="6.5"
                  ry="15"
                  fill="var(--tint-lilac)"
                  strokeWidth="2.2"
                  transform={`rotate(${angle}) translate(0 -11)`}
                />
              ))}
              <circle r="5.5" fill="var(--tint-saffron)" strokeWidth="2.2" />
            </g>
          </g>
        ))}

        {/* ---------------- land ---------------- */}
        <path
          d="M0 334 C80 324 160 346 250 336 C340 326 430 350 520 336 C556 330 580 332 600 330
             L600 420 L0 420 Z"
          fill="var(--tint-mint)"
        />

        {/* ---------------- jute stalks ---------------- */}
        <g transform="translate(24 226)" strokeWidth="2.4" fill="none">
          <path d="M26 146 C18 100 32 58 28 10" />
          <path d="M56 150 C54 108 66 74 64 40" />
          <g fill="var(--tint-mint)">
            <ellipse
              cx="6"
              cy="60"
              rx="22"
              ry="9"
              transform="rotate(-30 6 60)"
            />
            <ellipse
              cx="46"
              cy="30"
              rx="22"
              ry="9"
              transform="rotate(24 46 30)"
            />
            <ellipse
              cx="86"
              cy="72"
              rx="22"
              ry="9"
              transform="rotate(30 86 72)"
            />
            <ellipse
              cx="10"
              cy="106"
              rx="20"
              ry="8.5"
              transform="rotate(-22 10 106)"
            />
            <ellipse
              cx="82"
              cy="118"
              rx="20"
              ry="8.5"
              transform="rotate(26 82 118)"
            />
          </g>
        </g>

        {/* ---------------- terracotta pots ---------------- */}
        <g transform="translate(88 300)">
          <ellipse cx="46" cy="70" rx="46" ry="38" fill="var(--tint-peach)" />
          <path d="M30 24 L62 24 L57 38 L35 38 Z" fill="var(--tint-peach)" />
          <ellipse cx="46" cy="23" rx="21" ry="7" fill="var(--tint-saffron)" />
          <path
            d="M8 62 Q46 80 84 62"
            fill="none"
            strokeWidth="2"
            strokeDasharray="6 7"
            opacity="0.6"
          />
          <path
            d="M16 86 Q46 98 76 86"
            fill="none"
            strokeWidth="2"
            opacity="0.45"
          />

          <ellipse cx="110" cy="84" rx="29" ry="25" fill="var(--tint-peach)" />
          <ellipse cx="110" cy="60" rx="13" ry="5" fill="var(--tint-saffron)" />
          <path
            d="M86 80 Q110 92 134 80"
            fill="none"
            strokeWidth="2"
            strokeDasharray="5 6"
            opacity="0.55"
          />
        </g>

        {/* ---------------- kantha-stitched textile stack ---------------- */}
        <g transform="translate(392 330)">
          <rect
            x="0"
            y="52"
            width="172"
            height="28"
            rx="14"
            fill="var(--tint-lilac)"
          />
          <rect
            x="12"
            y="24"
            width="148"
            height="28"
            rx="14"
            fill="var(--tint-rose)"
          />
          <rect
            x="26"
            y="-4"
            width="122"
            height="28"
            rx="14"
            fill="var(--tint-saffron)"
          />
          {/* nakshi kantha: the running stitch that gives the quilt its name */}
          <g strokeWidth="2" strokeDasharray="7 6" opacity="0.55">
            <path d="M14 66 L158 66" />
            <path d="M26 38 L146 38" />
            <path d="M40 10 L134 10" />
          </g>
        </g>

        {/* ---------------- alpona flourish ---------------- */}
        <g
          fill="none"
          strokeWidth="2"
          opacity="0.4"
          transform="translate(16 18)"
        >
          <path d="M0 40 A40 40 0 0 1 40 0" strokeDasharray="3 8" />
          <path d="M0 22 A22 22 0 0 1 22 0" />
        </g>
      </g>
    </svg>
  );
}
