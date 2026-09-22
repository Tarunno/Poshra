/**
 * Craft motifs drawn as inline SVG.
 *
 * Kantha quilts are built from a plain running stitch, so the same idea runs
 * through the interface: dashes for stitches, an occasional cross-stitch knot,
 * and simple tools of the trade. Each motif inherits `currentColor`, so it
 * takes the colour of whatever it sits in.
 */

type MotifProps = { className?: string };

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** Needle pulling thread: the gesture behind every hand-stitched piece. */
export function NeedleThread({ className }: MotifProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <path d="M20.5 3.5 L10 14" />
      <path d="M8.6 15.4 L7 20 L11.6 18.4 Z" />
      <ellipse
        cx="19.2"
        cy="4.8"
        rx="1.5"
        ry="1"
        transform="rotate(-45 19.2 4.8)"
      />
      <path
        d="M4 20 C7 16 2 13 5 9.5 C7 7 5.5 5 3.5 4.5"
        strokeDasharray="2.6 2.4"
      />
    </svg>
  );
}

/** Thread spool. */
export function Spool({ className }: MotifProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <path d="M6 3 h12 M6 21 h12" />
      <path d="M8 3 v18 M16 3 v18" />
      <path
        d="M8 7.5 h8 M8 11 h8 M8 14.5 h8 M8 18 h8"
        strokeDasharray="2.5 2"
      />
    </svg>
  );
}

/** Weaver's shuttle: it carries the weft through the warp on a handloom. */
export function Shuttle({ className }: MotifProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <path d="M1.5 12 L6.5 8.5 H17.5 L22.5 12 L17.5 15.5 H6.5 Z" />
      <rect x="9" y="10" width="6" height="4" rx="1" />
      <path d="M12 10 v4" />
      <path d="M22.5 12 h-2.5" strokeDasharray="2 2" />
    </svg>
  );
}

/** Interlaced warp and weft: the weave itself, legible at small sizes. */
export function Weave({ className }: MotifProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <path d="M9 3 v18 M15 3 v18 M3 9 h18 M3 15 h18" />
      <path d="M6 6 h3 v3 h-3 Z M12 6 h3 v3 h-3 Z M9 12 h3 v3 h-3 Z M15 12 h3 v3 h-3 Z M6 15 h3 v3 h-3 Z M12 15 h3 v3 h-3 Z" />
    </svg>
  );
}

/** Embroidery hoop holding stretched cloth. */
export function Hoop({ className }: MotifProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <circle cx="12" cy="13" r="8.5" />
      <circle cx="12" cy="13" r="6.2" strokeDasharray="2.6 2.4" />
      <path d="M10 4.5 h4 v1.8 h-4 Z" />
      <path d="M9.5 13 q2.5 -3 5 0" />
    </svg>
  );
}

/** Potter's wheel with a pot taking shape. */
export function PottersWheel({ className }: MotifProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <ellipse cx="12" cy="19" rx="9" ry="2.6" />
      <path d="M12 16.5 v2.5" />
      <path d="M8.5 8 h7 l-1 2.2 c2.4 1.2 2.6 5 -2.5 5.3 c-5.1 -0.3 -4.9 -4.1 -2.5 -5.3 Z" />
    </svg>
  );
}

/** A hand: the work is made by one. */
export function MakersHand({ className }: MotifProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <path d="M9 12.5 V5.2 a1.4 1.4 0 0 1 2.8 0 V11" />
      <path d="M11.8 11 V4.2 a1.4 1.4 0 0 1 2.8 0 V11" />
      <path d="M14.6 11 V6 a1.4 1.4 0 0 1 2.8 0 v7.5 c0 4.2 -2.4 7 -6 7 c-3 0 -4.6 -1.6 -5.6 -4.2 L4 13.2 a1.4 1.4 0 0 1 2.3 -1.5 L9 14" />
    </svg>
  );
}

/**
 * A running-stitch rule, the way a kantha seam separates panels.
 * Decorative only, so it is hidden from assistive tech.
 */
export function StitchDivider({ className }: MotifProps) {
  return (
    <div className={className} aria-hidden>
      <svg className="h-3 w-full" preserveAspectRatio="none">
        <line
          x1="0"
          y1="6"
          x2="100%"
          y2="6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="10 9"
          opacity="0.45"
        />
      </svg>
    </div>
  );
}

/**
 * A stitched border strip: running stitch with a cross-stitch knot every few
 * repeats, like the edging on a kantha throw.
 *
 * The motif is a repeating `<pattern>` rather than a stretched path, so the
 * stitches keep their shape at any width.
 */
export function KanthaRule({ className }: MotifProps) {
  return (
    <svg className={className} aria-hidden preserveAspectRatio="none">
      <defs>
        <pattern
          id="kantha-rule"
          width="104"
          height="16"
          patternUnits="userSpaceOnUse"
        >
          <g
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            opacity="0.55"
          >
            <path d="M0 8 H104" strokeDasharray="8 7" />
            <path d="M46 4.5 L54 11.5 M54 4.5 L46 11.5" opacity="0.85" />
          </g>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#kantha-rule)" />
    </svg>
  );
}
