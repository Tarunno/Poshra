/**
 * The Poshra mark: a nagordola (নাগরদোলা).
 *
 * The hand-cranked wooden wheel at a village mela — the fair where traders lay
 * out their poshra. Four seats ride the rim in the marketplace's own tints,
 * and the ground it stands on is a running stitch, tying the mark to the
 * kantha stitching used across the interface.
 *
 * Colours come from the theme tokens, so the mark follows the palette instead
 * of shipping fixed brand colours.
 */

type Props = { className?: string };

const RADIUS = 9.8;
const CENTER = { x: 16, y: 14 };

const SEATS = [
  { angle: -45, fill: "var(--tint-rose)" },
  { angle: 45, fill: "var(--tint-mint)" },
  { angle: 135, fill: "var(--tint-lilac)" },
  { angle: 225, fill: "var(--tint-sky)" },
];

const point = (angle: number) => ({
  x: CENTER.x + RADIUS * Math.cos((angle * Math.PI) / 180),
  y: CENTER.y + RADIUS * Math.sin((angle * Math.PI) / 180),
});

export function PoshraMark({ className }: Props) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <g
        stroke="var(--app-fg)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      >
        {/* frame: two legs planted on stitched ground */}
        <path d="M16 14 L9 27.4 M16 14 L23 27.4" />
        <path d="M5.4 27.4 H26.6" strokeDasharray="3 3" opacity="0.7" />

        {/* the wheel */}
        <circle
          cx={CENTER.x}
          cy={CENTER.y}
          r={RADIUS}
          fill="var(--tint-saffron)"
        />

        {/* spokes */}
        {SEATS.map(({ angle }) => {
          const { x, y } = point(angle);
          return (
            <line
              key={angle}
              x1={CENTER.x}
              y1={CENTER.y}
              x2={x}
              y2={y}
              strokeWidth="1.2"
            />
          );
        })}

        {/* seats riding the rim */}
        {SEATS.map(({ angle, fill }) => {
          const { x, y } = point(angle);
          return (
            <circle
              key={angle}
              cx={x}
              cy={y}
              r="2.7"
              fill={fill}
              strokeWidth="1.35"
            />
          );
        })}

        {/* hub */}
        <circle
          cx={CENTER.x}
          cy={CENTER.y}
          r="2"
          fill="var(--tint-peach)"
          strokeWidth="1.35"
        />
      </g>
    </svg>
  );
}

/** Mark plus wordmark, for the header and footer. */
export function PoshraLogo({ className }: Props) {
  return (
    <span className={className}>
      <PoshraMark className="size-9 shrink-0" />
      <span className="text-xl font-extrabold tracking-tight">poshra</span>
    </span>
  );
}
