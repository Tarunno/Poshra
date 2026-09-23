/**
 * Prices in a form are typed in major units; everything else in Poshra stores
 * minor units as integers. This is the one place the two meet.
 *
 * The exponent comes from Intl rather than a hard-coded 100, because it is not
 * two everywhere: JPY has none, and a hard-coded hundred would silently
 * multiply a yen price by a hundred.
 */
function exponent(currency: string): number {
  return (
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
    }).resolvedOptions().maximumFractionDigits ?? 2
  );
}

/** "5,600.50" in BDT → 560050. Null when it is not a usable price. */
export function toMinorUnits(value: string, currency: string): number | null {
  const cleaned = value.replace(/[\s,]/g, "");
  if (!/^\d+(\.\d+)?$/.test(cleaned)) return null;

  const digits = exponent(currency);
  const [whole, fraction = ""] = cleaned.split(".");
  if (fraction.length > digits) return null; // more precision than the currency has

  const minor =
    Number(whole) * 10 ** digits + Number(fraction.padEnd(digits, "0") || 0);
  return Number.isSafeInteger(minor) ? minor : null;
}

/** 560050 in BDT → "5600.50", for filling the field back in. */
export function toMajorUnits(minor: number, currency: string): string {
  const digits = exponent(currency);
  return (minor / 10 ** digits).toFixed(digits);
}
