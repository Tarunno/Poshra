/**
 * Money and date formatting.
 *
 * Prices arrive as integer minor units plus an ISO 4217 code, never floats.
 * The number of minor units per major unit differs by currency (two for BDT
 * and USD, zero for JPY), so the exponent comes from Intl rather than a
 * hard-coded 100.
 */

const formatters = new Map<string, Intl.NumberFormat>();

function formatter(currency: string, locale: string): Intl.NumberFormat {
  const key = `${locale}:${currency}`;
  let cached = formatters.get(key);
  if (!cached) {
    cached = new Intl.NumberFormat(locale, { style: "currency", currency });
    formatters.set(key, cached);
  }
  return cached;
}

export function formatMoney(
  minor: number,
  currency: string,
  locale = "en-US",
): string {
  const fmt = formatter(currency, locale);
  const digits = fmt.resolvedOptions().maximumFractionDigits ?? 2;
  return fmt.format(minor / 10 ** digits);
}

export function formatLeadTime(days: number): string {
  if (days <= 1) return "Ships next day";
  if (days <= 7) return `Ships in ${days} days`;
  const weeks = Math.round(days / 7);
  return `Made to order · about ${weeks} week${weeks > 1 ? "s" : ""}`;
}
