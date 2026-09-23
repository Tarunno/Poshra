/**
 * Money and date formatting.
 *
 * Prices arrive as integer minor units plus an ISO 4217 code, never floats.
 * The number of minor units per major unit differs by currency (two for BDT
 * and USD, zero for JPY), so the exponent comes from Intl rather than a
 * hard-coded 100.
 */

const formatters = new Map<string, Intl.NumberFormat>();

function formatter(
  currency: string,
  locale: string,
  fractionDigits?: number,
): Intl.NumberFormat {
  const key = `${locale}:${currency}:${fractionDigits ?? "auto"}`;
  let cached = formatters.get(key);
  if (!cached) {
    cached = new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      // The symbol alone (৳, $) reads as a price; the ISO code reads as a
      // spreadsheet.
      currencyDisplay: "narrowSymbol",
      ...(fractionDigits === undefined
        ? {}
        : {
            minimumFractionDigits: fractionDigits,
            maximumFractionDigits: fractionDigits,
          }),
    });
    formatters.set(key, cached);
  }
  return cached;
}

/**
 * Format an integer amount of minor units.
 *
 * Whole amounts drop the decimals (৳5,600 rather than ৳5,600.00) while
 * fractional ones keep them (৳5,600.50).
 */
export function formatMoney(
  minor: number,
  currency: string,
  locale = "en-US",
): string {
  const digits =
    formatter(currency, locale).resolvedOptions().maximumFractionDigits ?? 2;
  const isWhole = minor % 10 ** digits === 0;
  return formatter(currency, locale, isWhole ? 0 : digits).format(
    minor / 10 ** digits,
  );
}

export function formatLeadTime(days: number): string {
  if (days <= 1) return "Ships next day";
  if (days <= 7) return `Ships in ${days} days`;
  const weeks = Math.round(days / 7);
  return `Made to order · about ${weeks} week${weeks > 1 ? "s" : ""}`;
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

/** "3 hours ago", "yesterday". Rendered per request, so it is never stale. */
export function formatRelativeTime(iso: string, now = Date.now()): string {
  const seconds = (new Date(iso).getTime() - now) / 1000;
  const magnitude = Math.abs(seconds);
  for (const [unit, size] of STEPS) {
    if (magnitude >= size)
      return relative.format(Math.round(seconds / size), unit);
  }
  return relative.format(Math.round(seconds), "second");
}

/** A short day label for chart axes: "14 Sep". */
export function formatDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}
