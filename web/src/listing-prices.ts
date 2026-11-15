import type { Detail } from "./types";
export type Auction = Detail["listings"][number];
export function unitBuyout(row: Auction): [bigint, bigint] | null {
  if (row.unit_price !== null) return [BigInt(row.unit_price), 1n];
  return row.buyout !== null
    ? [BigInt(row.buyout), BigInt(row.quantity)]
    : null;
}
export function stackBuyout(row: Auction): string | null {
  return (
    row.buyout ??
    (row.unit_price === null
      ? null
      : String(BigInt(row.unit_price) * BigInt(row.quantity)))
  );
}
export function compareUnits(a: Auction, b: Auction): number {
  const left = unitBuyout(a),
    right = unitBuyout(b);
  if (!left || !right) return left ? -1 : right ? 1 : 0;
  const difference = left[0] * right[1] - right[0] * left[1];
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}
export function compareCopper(a: string | null, b: string | null): number {
  if (a === null || b === null) return a === null ? (b === null ? 0 : 1) : -1;
  return BigInt(a) < BigInt(b) ? -1 : BigInt(a) > BigInt(b) ? 1 : 0;
}
export function durationLabel(value: string | null): string {
  return (
    (
      {
        SHORT: "Short remaining",
        MEDIUM: "Medium remaining",
        LONG: "Long remaining",
        VERY_LONG: "Very long remaining",
      } as Record<string, string>
    )[value || ""] || "Duration unavailable"
  );
}
