import type { DailyPoint } from "@/lib/sales";
import { formatDay, formatMoney } from "@/lib/format";

/**
 * Daily revenue over the reporting window.
 *
 * Columns rather than a line: each day is a discrete bucket, and most days on a
 * handmade marketplace are zero. A line drawn through those zeroes invents a
 * slope between them that never happened.
 *
 * One series, so there is no legend — the heading says what is plotted. Values
 * are not printed on every column; the peak is labelled, the axis carries the
 * scale, each column names itself on hover, and the table below has all thirty.
 */

const WIDTH = 420;
const PLOT_HEIGHT = 96;
const BASELINE = PLOT_HEIGHT + 1;
const GAP = 2; // the surface separating neighbours, never a stroke
const MAX_BAR = 24;
const RADIUS = 4;

/** A column: rounded at the data end, square where it meets the baseline. */
function columnPath(x: number, width: number, height: number): string {
  const top = BASELINE - height;
  const r = Math.min(RADIUS, width / 2, height);
  return [
    `M ${x} ${BASELINE}`,
    `L ${x} ${top + r}`,
    `Q ${x} ${top} ${x + r} ${top}`,
    `L ${x + width - r} ${top}`,
    `Q ${x + width} ${top} ${x + width} ${top + r}`,
    `L ${x + width} ${BASELINE}`,
    "Z",
  ].join(" ");
}

export function SalesChart({
  daily,
  currency,
}: {
  daily: DailyPoint[];
  currency: string;
}) {
  const peak = Math.max(...daily.map((day) => day.revenue_minor), 0);

  if (peak === 0) {
    return (
      <p className="mt-4 text-sm opacity-70">
        No sales in the last {daily.length} days yet.
      </p>
    );
  }

  const band = WIDTH / daily.length;
  const barWidth = Math.min(band - GAP, MAX_BAR);
  const best = daily.reduce((a, b) =>
    b.revenue_minor > a.revenue_minor ? b : a,
  );
  const selling = daily.filter((day) => day.revenue_minor > 0).length;

  return (
    <figure className="mt-5">
      <svg
        viewBox={`0 0 ${WIDTH} ${BASELINE + 18}`}
        className="h-auto w-full overflow-visible"
        role="img"
        aria-label={`Daily revenue over ${daily.length} days. Best day ${formatDay(best.date)} at ${formatMoney(best.revenue_minor, currency)}.`}
      >
        {/* One hairline at the peak and one at zero: enough to read the scale
            without a grid competing with the data. */}
        <line
          x1="0"
          x2={WIDTH}
          y1={BASELINE - PLOT_HEIGHT}
          y2={BASELINE - PLOT_HEIGHT}
          className="stroke-foreground/15"
          strokeWidth="1"
        />
        <line
          x1="0"
          x2={WIDTH}
          y1={BASELINE}
          y2={BASELINE}
          className="stroke-foreground/25"
          strokeWidth="1"
        />

        {daily.map((day, index) => {
          const height = (day.revenue_minor / peak) * PLOT_HEIGHT;
          const x = index * band + (band - barWidth) / 2;
          const label = `${formatDay(day.date)}: ${formatMoney(day.revenue_minor, currency)}`;

          return day.revenue_minor > 0 ? (
            <path
              key={day.date}
              d={columnPath(x, barWidth, height)}
              className="fill-chart-sales"
            >
              <title>{label}</title>
            </path>
          ) : (
            // A zero day still gets a hit target, so hovering a gap answers
            // "nothing sold" instead of nothing at all.
            <rect
              key={day.date}
              x={x}
              y={BASELINE - 2}
              width={barWidth}
              height="2"
              className="fill-foreground/15"
            >
              <title>{label}</title>
            </rect>
          );
        })}

        <text
          x="0"
          y={BASELINE + 14}
          className="fill-foreground/60 text-[10px]"
        >
          {formatDay(daily[0].date)}
        </text>
        <text
          x={WIDTH}
          y={BASELINE + 14}
          textAnchor="end"
          className="fill-foreground/60 text-[10px]"
        >
          {formatDay(daily[daily.length - 1].date)}
        </text>
      </svg>

      <figcaption className="mt-3 flex flex-wrap items-baseline justify-between gap-2 text-xs opacity-70">
        <span>
          Best day {formatDay(best.date)} ·{" "}
          <span className="font-semibold tabular-nums">
            {formatMoney(best.revenue_minor, currency)}
          </span>{" "}
          — the top of the axis
        </span>
        <span className="tabular-nums">
          {selling} of {daily.length} days with a sale
        </span>
      </figcaption>

      {/* Colour and hover are not the only way in: every figure here is also
          readable as text. */}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer font-semibold opacity-70 hover:opacity-100">
          View as a table
        </summary>
        <table className="mt-3 w-full text-left">
          <thead className="opacity-60">
            <tr>
              <th scope="col" className="py-1 font-medium">
                Day
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                Pieces
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                Revenue
              </th>
            </tr>
          </thead>
          <tbody>
            {daily
              .filter((day) => day.revenue_minor > 0)
              .map((day) => (
                <tr key={day.date} className="border-foreground/10 border-t">
                  <th scope="row" className="py-1 font-normal">
                    {formatDay(day.date)}
                  </th>
                  <td className="py-1 text-right tabular-nums">{day.pieces}</td>
                  <td className="py-1 text-right tabular-nums">
                    {formatMoney(day.revenue_minor, currency)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
