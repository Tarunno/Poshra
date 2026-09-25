import { formatMoney } from "@/lib/format";
import type { DailyTakings } from "@/lib/oversight";

/**
 * Takings across the whole marketplace, by day.
 *
 * Every day is a bar, including the ones where nothing sold — a chart drawn
 * only from days with sales slopes cheerfully upward through a quiet week,
 * because the quiet days are missing rather than flat.
 */
export function TakingsChart({ daily }: { daily: DailyTakings[] }) {
  const peak = Math.max(...daily.map((day) => day.takings_minor), 0);
  const total = daily.reduce((sum, day) => sum + day.takings_minor, 0);

  if (peak === 0) {
    return (
      <p className="mt-3 text-sm opacity-70">
        Nothing has sold in the last {daily.length} days. The chart starts with
        the first order.
      </p>
    );
  }

  return (
    <figure className="mt-4">
      <div className="flex h-28 items-end gap-[3px]" aria-hidden>
        {daily.map((day) => (
          <div
            key={day.date}
            title={`${day.date}: ${formatMoney(day.takings_minor, "BDT")}`}
            className="bg-ink-lilac/70 hover:bg-ink-lilac min-h-[2px] flex-1 rounded-t-sm transition-colors"
            style={{
              height: `${Math.max((day.takings_minor / peak) * 100, 1.5)}%`,
            }}
          />
        ))}
      </div>
      <figcaption className="mt-2 flex items-baseline justify-between text-xs opacity-60">
        <span>{daily[0]?.date}</span>
        <span className="font-semibold">
          {formatMoney(total, "BDT")} over {daily.length} days
        </span>
        <span>today</span>
      </figcaption>
    </figure>
  );
}

/** A small ranked list — artisans, or crafts. Bars rather than numbers alone,
 *  because the gap between first and second is the information. */
export function Ranking({
  rows,
  empty,
}: {
  rows: { name: string; takings_minor: number; pieces: number }[];
  empty: string;
}) {
  const peak = Math.max(...rows.map((row) => row.takings_minor), 0);
  if (rows.length === 0)
    return <p className="mt-2 text-sm opacity-60">{empty}</p>;

  return (
    <ol className="mt-3 space-y-2">
      {rows.map((row) => (
        <li key={row.name} className="space-y-1">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate">{row.name}</span>
            <span className="shrink-0 font-semibold tabular-nums">
              {formatMoney(row.takings_minor, "BDT")}
            </span>
          </div>
          <div className="bg-background/50 h-1.5 overflow-hidden rounded-full">
            <div
              className="bg-ink-mint/70 h-full rounded-full"
              style={{
                width: `${peak ? (row.takings_minor / peak) * 100 : 0}%`,
              }}
            />
          </div>
        </li>
      ))}
    </ol>
  );
}
