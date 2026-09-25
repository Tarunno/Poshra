/**
 * The drawing parts of the oversight board.
 *
 * Hand-drawn SVG, like the rest of Poshra's illustration: no chart library,
 * because everything here is one series and a library would be a dependency
 * that renders a different house style than the one the shop is drawn in.
 */

/** A smooth path through the points, rather than a zigzag between them.
 *  Catmull-Rom converted to cubic béziers: the curve passes through every
 *  reading, which a plain bézier does not. */
function curve(points: [number, number][]): string {
  if (points.length < 2) return "";
  const path = [`M ${points[0][0]} ${points[0][1]}`];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    path.push(
      `C ${p1[0] + (p2[0] - p0[0]) / 6} ${p1[1] + (p2[1] - p0[1]) / 6},` +
        ` ${p2[0] - (p3[0] - p1[0]) / 6} ${p2[1] - (p3[1] - p1[1]) / 6},` +
        ` ${p2[0]} ${p2[1]}`,
    );
  }
  return path.join(" ");
}

function plot(values: number[], width: number, height: number, pad = 4) {
  const peak = Math.max(...values, 1);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  return values.map(
    (value, i) =>
      [i * step, height - pad - (value / peak) * (height - pad * 2)] as [
        number,
        number,
      ],
  );
}

/** The hero chart: a filled curve with the last reading marked. */
export function AreaCurve({
  values,
  className = "text-ink-lilac",
  height = 150,
}: {
  values: number[];
  className?: string;
  height?: number;
}) {
  const width = 600;
  const points = plot(values, width, height, 10);
  const line = curve(points);
  const last = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={`h-[150px] w-full ${className}`}
      aria-hidden
    >
      <defs>
        <linearGradient id="under-the-curve" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.28" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d={`${line} L ${width} ${height} L 0 ${height} Z`}
        fill="url(#under-the-curve)"
      />
      <path
        d={line}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {last && <circle cx={last[0]} cy={last[1]} r="4" fill="currentColor" />}
    </svg>
  );
}

/** A small line for a stat card. Same curve, no fill, no axis. */
export function Sparkline({
  values,
  className = "text-ink-mint",
}: {
  values: number[];
  className?: string;
}) {
  const points = plot(values, 120, 34, 4);
  return (
    <svg
      viewBox="0 0 120 34"
      preserveAspectRatio="none"
      className={`h-8 w-full ${className}`}
      aria-hidden
    >
      <path
        d={curve(points)}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/**
 * A dial, drawn as a stitched arc.
 *
 * The track is dashed — the same running stitch the panels are bordered with —
 * so a gauge reads as part of this interface rather than as a chart pasted
 * into it.
 */
export function Dial({
  share,
  label,
  caption,
  className = "text-ink-mint",
}: {
  share: number;
  label: string;
  caption: string;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(1, share));
  const radius = 54;
  const sweep = Math.PI * radius; // half a circle
  const arc = `M 16 70 A ${radius} ${radius} 0 0 1 124 70`;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 140 84" className={`w-full max-w-[200px] ${className}`}>
        <path
          d={arc}
          fill="none"
          stroke="currentColor"
          strokeOpacity="0.22"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray="5 7"
        />
        <path
          d={arc}
          fill="none"
          stroke="currentColor"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={`${sweep * clamped} ${sweep}`}
        />
        <text
          x="70"
          y="66"
          textAnchor="middle"
          className="fill-current text-[26px] font-extrabold"
        >
          {Math.round(clamped * 100)}%
        </text>
      </svg>
      <p className="mt-1 text-sm font-semibold">{label}</p>
      <p className="text-xs opacity-60">{caption}</p>
    </div>
  );
}

/**
 * How this week compares with the one before it.
 *
 * A number on its own says what happened; a number beside last week's says
 * whether it is worth reading. Silent when there is nothing to compare to,
 * because "+100%" from a single sale is noise dressed as news.
 */
export function Trend({ now, before }: { now: number; before: number }) {
  if (before === 0 && now === 0) return null;
  if (before === 0) {
    return (
      <span className="bg-tint-mint text-ink-mint rounded-full px-2 py-0.5 text-xs font-semibold">
        new
      </span>
    );
  }
  const change = Math.round(((now - before) / before) * 100);
  const up = change >= 0;
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
        up ? "bg-tint-mint text-ink-mint" : "bg-tint-rose text-ink-rose"
      }`}
    >
      {up ? "↑" : "↓"} {Math.abs(change)}%
    </span>
  );
}
